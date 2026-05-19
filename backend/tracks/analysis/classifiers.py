"""Judgement-call estimators — valence, mood, genre, region.

Unlike the deterministic extractors, these features are *inferences*: in
industry they come from ML models trained on labelled datasets. We have no
dataset, so today every estimator below is a transparent, hand-tuned
heuristic over the engine's feature map.

ML-ready design
---------------
Every estimator implements one tiny contract:

    estimator.predict(features: dict, *, metadata: dict | None) -> result

``features`` is the flat numeric map produced by
:meth:`FeatureVector.as_feature_map` (plus the deterministic extractor
outputs). A trained model consumes the *same* map — so swapping a heuristic
for a model means writing a new subclass and registering it via the
``AUDIO_ANALYSIS_ESTIMATORS`` Django setting. No caller changes, no engine
changes.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Prediction:
    """A classifier result: the chosen label plus full scoring detail."""

    label: str
    confidence: float
    scores: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Base contracts
# ---------------------------------------------------------------------------
class BaseRegressor(ABC):
    """Estimates a continuous 0-1 score (e.g. valence)."""

    kind = "regressor"
    version = "heuristic-1"

    @abstractmethod
    def predict(self, features: dict, *, metadata: dict | None = None) -> float:
        ...


class BaseClassifier(ABC):
    """Estimates a categorical label (e.g. mood, genre, region)."""

    kind = "classifier"
    version = "heuristic-1"

    @abstractmethod
    def predict(self, features: dict, *, metadata: dict | None = None) -> Prediction:
        ...


def _range_score(value: float, lo: float, hi: float) -> float:
    """1.0 inside [lo, hi]; linear falloff outside; equality test if lo==hi."""
    if hi <= lo:  # discrete target (e.g. mode == 0)
        return 1.0 if round(value) == round(lo) else 0.0
    if lo <= value <= hi:
        return 1.0
    span = hi - lo
    distance = lo - value if value < lo else value - hi
    return max(0.0, 1.0 - distance / span)


# ---------------------------------------------------------------------------
# Valence — musical positivity (happy <-> sad)
# ---------------------------------------------------------------------------
class HeuristicValenceRegressor(BaseRegressor):
    """Valence from mode, brightness, tempo, harmonic consonance and energy.

    Major key + bright timbre + brisk tempo + clear consonant harmony reads
    as happy; minor key + dark + slow reads as sad.
    """

    def predict(self, features: dict, *, metadata: dict | None = None) -> float:
        mode_cue = 1.0 if features.get("mode", 1) == 1 else 0.35
        brightness_cue = features.get("brightness", 0.5)
        tempo_cue = float(np.clip((features.get("tempo_bpm", 100) - 60) / 100, 0, 1))
        consonance_cue = features.get("harmonic_ratio", 0.5) * features.get(
            "key_strength", 0.5
        )
        energy_cue = features.get("energy", 0.5)

        valence = (
            0.30 * mode_cue
            + 0.25 * brightness_cue
            + 0.20 * tempo_cue
            + 0.15 * consonance_cue
            + 0.10 * energy_cue
        )
        return round(float(np.clip(valence, 0.0, 1.0)), 4)


# ---------------------------------------------------------------------------
# Mood — energy x valence quadrant
# ---------------------------------------------------------------------------
# Prototype (energy, valence) coordinate of each mood. Labels match the
# rest of the app (tracks/services.py MOOD_SIGNATURES) so recommendations
# keep working. "focused" is the neutral centre / fallback.
_MOOD_PROTOTYPES = {
    "celebratory": (0.85, 0.85),
    "energized": (0.80, 0.55),
    "calm": (0.30, 0.62),
    "melancholic": (0.25, 0.25),
    "anxious": (0.68, 0.25),
    "focused": (0.50, 0.50),
}


class HeuristicMoodClassifier(BaseClassifier):
    """Nearest-prototype mood in the energy/valence plane."""

    def predict(self, features: dict, *, metadata: dict | None = None) -> Prediction:
        energy = features.get("energy", 0.5)
        valence = features.get("valence", 0.5)

        scores = {}
        for mood, (proto_e, proto_v) in _MOOD_PROTOTYPES.items():
            distance = np.hypot(energy - proto_e, valence - proto_v)
            # Max possible distance in the unit square is sqrt(2).
            scores[mood] = round(float(1.0 - distance / np.sqrt(2)), 4)

        label = max(scores, key=scores.get)
        return Prediction(label=label, confidence=scores[label], scores=scores)


# ---------------------------------------------------------------------------
# Genre — soft-matching against hand-tuned DSP profiles
# ---------------------------------------------------------------------------
# Each profile is a list of (feature, low, high, weight). A track scores
# high for a genre when its features land inside those ranges. Tuned for
# this catalogue (Indian + Western pop/rock); approximate by design.
_GENRE_PROFILES = {
    "electronic": [
        ("energy", 0.60, 1.00, 2.0), ("percussive_ratio", 0.40, 1.00, 1.5),
        ("acousticness", 0.00, 0.35, 1.5), ("spectral_flatness", 0.20, 1.00, 1.0),
        ("pulse_clarity", 0.40, 1.00, 1.0), ("tempo_bpm", 115, 140, 0.8),
    ],
    "rock": [
        ("energy", 0.60, 1.00, 2.0), ("percussive_ratio", 0.35, 0.80, 1.2),
        ("acousticness", 0.00, 0.45, 1.0), ("instrumentalness", 0.00, 0.60, 0.5),
        ("tempo_bpm", 95, 165, 0.8), ("brightness", 0.35, 0.85, 0.8),
    ],
    "hiphop": [
        ("energy", 0.40, 0.85, 1.2), ("low_freq_ratio", 0.50, 1.00, 2.0),
        ("tempo_bpm", 70, 110, 1.5), ("percussive_ratio", 0.35, 0.90, 1.0),
        ("pulse_clarity", 0.40, 1.00, 0.8),
    ],
    "pop": [
        ("energy", 0.45, 0.85, 1.5), ("valence", 0.45, 1.00, 1.0),
        ("brightness", 0.35, 0.80, 1.0), ("tempo_bpm", 95, 135, 1.0),
        ("vocal_band_ratio", 0.25, 0.60, 0.8),
    ],
    "classical": [
        ("acousticness", 0.55, 1.00, 2.0), ("instrumentalness", 0.50, 1.00, 2.0),
        ("harmonic_ratio", 0.55, 1.00, 1.5), ("dynamic_range", 0.40, 1.00, 1.2),
        ("percussive_ratio", 0.00, 0.35, 1.0),
    ],
    "acoustic": [
        ("acousticness", 0.60, 1.00, 2.0), ("instrumentalness", 0.00, 0.55, 0.6),
        ("percussive_ratio", 0.00, 0.45, 1.0), ("energy", 0.15, 0.60, 1.0),
        ("spectral_flatness", 0.00, 0.40, 0.8),
    ],
    "lofi": [
        ("energy", 0.20, 0.55, 1.5), ("tempo_bpm", 60, 95, 1.3),
        ("brightness", 0.00, 0.45, 1.5), ("dynamic_range", 0.00, 0.45, 1.0),
        ("low_freq_ratio", 0.45, 1.00, 0.8),
    ],
    "ghazal": [
        ("acousticness", 0.45, 1.00, 1.5), ("energy", 0.15, 0.55, 1.5),
        ("tempo_bpm", 55, 95, 1.3), ("mode", 0, 0, 1.0),
        ("vocal_band_ratio", 0.30, 1.00, 1.0),
    ],
    "bollywood": [
        ("energy", 0.40, 0.85, 1.0), ("vocal_band_ratio", 0.28, 0.70, 1.5),
        ("brightness", 0.30, 0.78, 0.8), ("tempo_bpm", 85, 150, 0.6),
        ("acousticness", 0.20, 0.70, 0.6), ("pulse_clarity", 0.35, 1.00, 0.6),
    ],
    "ambient": [
        ("energy", 0.00, 0.35, 2.0), ("percussive_ratio", 0.00, 0.30, 1.5),
        ("instrumentalness", 0.55, 1.00, 1.5), ("acousticness", 0.35, 1.00, 0.8),
        ("tempo_bpm", 40, 95, 0.5),
    ],
}


class HeuristicGenreClassifier(BaseClassifier):
    """Genre by best-matching DSP profile (soft range scoring)."""

    def predict(self, features: dict, *, metadata: dict | None = None) -> Prediction:
        scores = {}
        for genre, profile in _GENRE_PROFILES.items():
            weighted_sum, weight_total = 0.0, 0.0
            for feature, lo, hi, weight in profile:
                value = features.get(feature)
                if value is None:
                    continue
                weighted_sum += weight * _range_score(float(value), lo, hi)
                weight_total += weight
            scores[genre] = round(weighted_sum / weight_total, 4) if weight_total else 0.0

        label = max(scores, key=scores.get)
        return Prediction(label=label, confidence=scores[label], scores=scores)


# ---------------------------------------------------------------------------
# Region — metadata-driven (with a low-confidence audio fallback)
# ---------------------------------------------------------------------------
# Region is fundamentally metadata, not audio: language is the strongest
# signal. Audio only offers weak scale-system clues.
_LANGUAGE_REGION = {
    "hindi": "India", "urdu": "India", "bhojpuri": "India", "bengali": "India",
    "punjabi": "Punjab", "marathi": "Maharashtra", "gujarati": "Gujarat",
    "tamil": "South India", "telugu": "South India",
    "kannada": "South India", "malayalam": "South India",
    "english": "US/UK", "spanish": "Latin America", "portuguese": "Latin America",
    "korean": "Korea", "japanese": "Japan", "chinese": "East Asia",
    "french": "Europe", "german": "Europe", "arabic": "Middle East",
}


class HeuristicRegionClassifier(BaseClassifier):
    """Region from track metadata (language); audio only as a weak fallback."""

    def predict(self, features: dict, *, metadata: dict | None = None) -> Prediction:
        metadata = metadata or {}
        language = (metadata.get("language") or "").strip().lower()
        if language in _LANGUAGE_REGION:
            region = _LANGUAGE_REGION[language]
            return Prediction(label=region, confidence=0.9, scores={region: 0.9})

        # No language metadata: audio carries only faint regional clues.
        # We surface a guess at low confidence rather than inventing data.
        return Prediction(label="Unknown", confidence=0.1, scores={"Unknown": 0.1})


# ---------------------------------------------------------------------------
# Registry — the single place to swap a heuristic for a trained model
# ---------------------------------------------------------------------------
_DEFAULT_ESTIMATORS = {
    "valence": HeuristicValenceRegressor(),
    "mood": HeuristicMoodClassifier(),
    "genre": HeuristicGenreClassifier(),
    "region": HeuristicRegionClassifier(),
}


def get_estimator(kind: str):
    """Return the estimator for ``kind`` (valence/mood/genre/region).

    A trained replacement can be registered without code changes by adding
    to ``settings.AUDIO_ANALYSIS_ESTIMATORS`` a dotted import path, e.g.::

        AUDIO_ANALYSIS_ESTIMATORS = {
            "genre": "tracks.analysis.models.CnnGenreClassifier",
        }
    """
    try:
        from django.conf import settings
        from django.utils.module_loading import import_string

        override = getattr(settings, "AUDIO_ANALYSIS_ESTIMATORS", None) or {}
        if kind in override:
            return import_string(override[kind])()
    except Exception:  # pragma: no cover - fall back to the heuristic
        logger.warning("Estimator override for %r failed; using heuristic", kind)

    return _DEFAULT_ESTIMATORS[kind]
