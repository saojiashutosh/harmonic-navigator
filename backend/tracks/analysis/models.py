"""Trained-model estimators that plug into the engine's classifier interface.

A ``.joblib`` model in ``tracks/analysis/trained/`` is picked up
automatically by the runtime — no settings change required. If the model
file is missing the wrapper falls back transparently to the corresponding
heuristic estimator, so the engine works in every state.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from .classifiers import (
    BaseClassifier,
    BaseRegressor,
    HeuristicGenreClassifier,
    HeuristicValenceRegressor,
    Prediction,
)
from .training import FEATURE_NAMES, MODELS_DIR

logger = logging.getLogger(__name__)


def _try_load(path: Path):
    if not path.exists():
        return None
    try:
        import joblib
        return joblib.load(path)
    except Exception as exc:
        logger.warning("Could not load trained model %s: %s", path, exc)
        return None


def _features_to_array(features: dict) -> np.ndarray:
    return np.array(
        [[float(features.get(name, 0.0)) for name in FEATURE_NAMES]],
        dtype=float,
    )


class ModelValenceRegressor(BaseRegressor):
    """Predicts valence with a trained sklearn regressor; heuristic fallback."""

    version = "model-1"

    def __init__(self):
        self.model = _try_load(MODELS_DIR / "valence.joblib")
        self._fallback = HeuristicValenceRegressor() if self.model is None else None
        if self.model is not None:
            logger.info("ModelValenceRegressor: using trained valence.joblib")

    def predict(self, features: dict, *, metadata: dict | None = None) -> float:
        if self.model is None:
            return self._fallback.predict(features, metadata=metadata)
        pred = float(self.model.predict(_features_to_array(features))[0])
        return round(float(np.clip(pred, 0.0, 1.0)), 4)


# ---------------------------------------------------------------------------
# Hybrid overlay: turn Western-trained genre into Indian-catalogue buckets
# ---------------------------------------------------------------------------
_INDIAN_LANGUAGES = {
    "hindi", "urdu", "punjabi", "marathi", "bengali", "tamil", "telugu",
    "kannada", "malayalam", "gujarati", "bhojpuri", "assamese", "odia",
    "haryanvi", "rajasthani",
}


def _hybrid_overlay(prediction: Prediction, features: dict, metadata: dict | None) -> Prediction:
    """Map a Western-trained genre to the engine's Indian-aware bucket set.

    Indian-language songs default to **bollywood**, with two specific
    overrides: ghazal (slow + minor + acoustic + vocal-forward) and lofi
    (slow + dark + narrow dynamics). For non-Indian languages the
    model's prediction stands, except that lofi can still be detected
    from the audio signature alone (lofi is a Western micro-genre too).
    """
    metadata = metadata or {}
    language = (metadata.get("language") or "").strip().lower()
    is_indian = language in _INDIAN_LANGUAGES
    # Era hint — pre-1990 Indian recordings are far more likely to be
    # ghazal/classical than modern Bollywood, so we relax the tempo gate
    # a little for old tracks.
    release_year = metadata.get("release_year")
    era_old = release_year is not None and release_year < 1990

    tempo = features.get("tempo_bpm", 0)
    mode = features.get("mode", 1)
    acousticness = features.get("acousticness", 0.5)
    brightness = features.get("brightness", 0.5)
    dynamic_range = features.get("dynamic_range", 0.5)
    vocal = features.get("vocal_band_ratio", 0.0)

    overlay_scores = dict(prediction.scores)

    # 1. Ghazal — slow, minor-mode, vocal-forward acoustic in an Indian
    #    language. Old recordings get a looser tempo gate.
    ghazal_tempo_cap = 115 if (is_indian and era_old) else 105
    if (is_indian and mode == 0 and tempo < ghazal_tempo_cap
            and acousticness >= 0.45 and vocal >= 0.30):
        overlay_scores["_overlay"] = (
            "indian-old-slow-minor" if era_old else "indian-slow-minor"
        )
        return Prediction("ghazal", min(0.85, prediction.confidence + 0.10),
                          overlay_scores)

    # 2. Lofi — slow + dark + narrow dynamics, when the model already
    #    landed in a calm-leaning bucket. Works regardless of language.
    if (tempo < 95 and brightness < 0.45 and dynamic_range < 0.45
            and prediction.label in {"acoustic", "ambient", "pop"}):
        overlay_scores["_overlay"] = "slow-dark-narrow"
        return Prediction("lofi", min(0.80, prediction.confidence + 0.05),
                          overlay_scores)

    # 3. Bollywood — default for any Indian-language song the model couldn't
    #    confidently place in a music-specific bucket (or placed in a
    #    Western bucket that's structurally a Bollywood mainstream song).
    #    Skip if the model is very sure of a strongly-genre-specific label.
    _STRONG_NONBOLLYWOOD = {"classical", "ambient"}
    if is_indian and (
        prediction.label not in _STRONG_NONBOLLYWOOD
        or prediction.confidence < 0.55
    ):
        overlay_scores["_overlay"] = f"indian-from-{prediction.label}"
        return Prediction("bollywood", min(0.85, prediction.confidence + 0.10),
                          overlay_scores)

    return prediction


class ModelGenreClassifier(BaseClassifier):
    """Trained sklearn classifier + Indian-catalogue overlay; heuristic fallback."""

    version = "model-1"

    def __init__(self):
        self.model = _try_load(MODELS_DIR / "genre.joblib")
        self._fallback = HeuristicGenreClassifier() if self.model is None else None
        if self.model is not None:
            logger.info("ModelGenreClassifier: using trained genre.joblib")

    def predict(self, features: dict, *, metadata: dict | None = None) -> Prediction:
        if self.model is None:
            base = self._fallback.predict(features, metadata=metadata)
        else:
            arr = _features_to_array(features)
            probs = self.model.predict_proba(arr)[0]
            classes = list(self.model.classes_)
            scores = {c: round(float(p), 4) for c, p in zip(classes, probs)}
            best = int(np.argmax(probs))
            base = Prediction(label=classes[best],
                              confidence=float(probs[best]),
                              scores=scores)
        return _hybrid_overlay(base, features, metadata)
