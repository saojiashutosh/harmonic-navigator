"""Build-time helpers for the audio engine's trained models.

Used by the ``build_training_dataset`` and ``train_audio_models`` commands:
canonical feature ordering, dataset JSONL I/O, Spotify→engine genre
mapping, and a feature-signal probe. Nothing here is needed at inference
time — the runtime model classes live in :mod:`tracks.analysis.models`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import numpy as np

_BASE = Path(__file__).resolve().parent
DATASET_DIR = _BASE / "training_data"
MODELS_DIR = _BASE / "trained"

# Canonical feature-vector layout: 21 DSP scalars + 12 chroma + 13 MFCC + 4
# extractor outputs = 50 numeric features in a fixed order. Every model is
# trained and queried using exactly this order, so the runtime never has to
# guess column meanings.
FEATURE_NAMES: list[str] = [
    # FeatureVector scalars (in the same order as FeatureVector._SCALAR_KEYS)
    "rms_mean", "rms_std", "dynamic_range", "loudness_db",
    "brightness", "spectral_rolloff", "spectral_bandwidth",
    "spectral_flatness", "spectral_contrast", "zero_crossing_rate",
    "tempo_bpm", "beat_strength", "onset_rate", "pulse_clarity",
    "harmonic_ratio", "percussive_ratio", "low_freq_ratio",
    "vocal_band_ratio", "key", "mode", "key_strength",
    # Pitch-class profile
    *[f"chroma_{i}" for i in range(12)],
    # Timbre fingerprint
    *[f"mfcc_{i}" for i in range(13)],
    # Extractor outputs (computed, calibrated-or-raw depending on caller)
    "energy", "acousticness", "instrumentalness", "loudness",
]


def feature_dict_from_result(result: dict) -> dict:
    """Flatten an ``analyze_audio_bytes`` result into ``{FEATURE_NAMES: float}``."""
    fv = result["featureVector"]
    out: dict[str, float] = {}
    for name in FEATURE_NAMES:
        if name.startswith("chroma_"):
            idx = int(name.split("_")[1])
            chroma = fv.get("chroma") or []
            out[name] = float(chroma[idx]) if idx < len(chroma) else 0.0
        elif name.startswith("mfcc_"):
            idx = int(name.split("_")[1])
            mfcc = fv.get("mfcc") or []
            out[name] = float(mfcc[idx]) if idx < len(mfcc) else 0.0
        elif name in fv:
            out[name] = float(fv[name])
        elif name in result:
            out[name] = float(result[name])
        else:
            out[name] = 0.0
    return out


def features_to_array(feature_dict: dict) -> np.ndarray:
    """Return a 1-D numpy row in the canonical column order."""
    return np.array(
        [float(feature_dict.get(name, 0.0)) for name in FEATURE_NAMES],
        dtype=float,
    )


# ---------------------------------------------------------------------------
# Spotify track_genre  ->  engine bucket
# ---------------------------------------------------------------------------
_GENRE_BUCKETS = {
    "electronic": [
        "edm", "electronic", "electro", "house", "deep-house", "chicago-house",
        "progressive-house", "techno", "detroit-techno", "minimal-techno",
        "trance", "dubstep", "drum-and-bass", "breakbeat", "hardstyle",
        "idm", "garage", "club", "dance", "j-dance", "industrial",
        "hardcore", "dub", "synth-pop",
    ],
    "rock": [
        "rock", "rock-n-roll", "hard-rock", "alt-rock", "alternative",
        "indie", "grunge", "psych-rock", "punk", "punk-rock", "emo",
        "goth", "j-rock", "power-pop", "metal", "heavy-metal",
        "death-metal", "black-metal", "metalcore", "grindcore", "rockabilly",
    ],
    "pop": [
        "pop", "j-pop", "k-pop", "cantopop", "mandopop", "indie-pop",
        "disco", "latino", "latin", "reggaeton", "dancehall", "brazil",
        "mpb", "samba", "party", "pop-film", "romance",
    ],
    "hiphop": [
        "hip-hop", "trip-hop", "r-n-b", "soul", "funk", "groove",
    ],
    "classical": [
        "classical", "opera", "piano",
    ],
    "acoustic": [
        "acoustic", "folk", "country", "bluegrass", "blues",
        "singer-songwriter", "songwriter", "guitar", "honky-tonk", "gospel",
    ],
    "ambient": [
        "ambient", "chill", "new-age", "sleep", "study", "sad", "show-tunes",
    ],
}

GENRE_BUCKET_MAP: dict[str, str] = {
    spotify_genre: bucket
    for bucket, genres in _GENRE_BUCKETS.items()
    for spotify_genre in genres
}

# Indian/regional and overly-generic labels — skipped during sampling
# because bollywood/ghazal/lofi are handled by the metadata overlay
# rather than by the model itself.
GENRE_SKIP = {
    "indian", "anime", "children", "kids", "disney", "comedy", "happy",
    "iranian", "malay", "spanish", "turkish", "swedish", "british",
    "french", "german", "world-music", "tango", "ska", "afrobeat",
    "salsa", "sertanejo", "pagode", "forro",
}


def bucket_for_genre(spotify_genre: str) -> str | None:
    g = (spotify_genre or "").strip().lower()
    if not g or g in GENRE_SKIP:
        return None
    return GENRE_BUCKET_MAP.get(g)


GENRE_BUCKETS: list[str] = list(_GENRE_BUCKETS.keys())


# ---------------------------------------------------------------------------
# JSONL I/O
# ---------------------------------------------------------------------------
def save_jsonl(rows: Iterable[dict], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
            n += 1
    return n


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# Signal probes — does the data even carry the signal?
# ---------------------------------------------------------------------------
def signal_probe_regression(rows: list[dict], target_key: str) -> list[tuple[str, float]]:
    """Pearson r of each feature against a numeric target. Sorted by |r| desc."""
    if not rows:
        return []
    targets = np.array([r[target_key] for r in rows], dtype=float)
    feats = [r["features"] for r in rows]
    out: list[tuple[str, float]] = []
    for name in FEATURE_NAMES:
        col = np.array([f.get(name, 0.0) for f in feats], dtype=float)
        if np.std(col) < 1e-9:
            continue
        r = float(np.corrcoef(col, targets)[0, 1])
        out.append((name, r))
    out.sort(key=lambda x: abs(x[1]), reverse=True)
    return out


def signal_probe_classification(rows: list[dict], target_key: str) -> list[tuple[str, float]]:
    """ANOVA F-score of each feature against a categorical target."""
    if not rows:
        return []
    from sklearn.feature_selection import f_classif

    X = np.array([[r["features"].get(n, 0.0) for n in FEATURE_NAMES]
                  for r in rows], dtype=float)
    y = np.array([r[target_key] for r in rows])
    f_scores, _ = f_classif(X, y)
    out = [(name, float(score) if not np.isnan(score) else 0.0)
           for name, score in zip(FEATURE_NAMES, f_scores)]
    out.sort(key=lambda x: x[1], reverse=True)
    return out
