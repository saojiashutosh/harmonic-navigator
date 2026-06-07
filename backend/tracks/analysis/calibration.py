"""Calibration layer — nudge engine outputs toward measured references.

The engine's feature formulas use hand-tuned constants. This module applies
a per-feature **affine correction** (``corrected = slope * value + intercept``)
that is fitted *offline* by the ``calibrate_audio_engine`` management command
against the Spotify-measured feature columns in ``data/*_songs.csv``.

At runtime this is pure arithmetic over a tiny JSON profile — no dataset, no
network. If ``calibration.json`` is absent every correction is the identity,
so the engine runs perfectly well uncalibrated too.
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

# The fitted profile lives next to this module.
CALIBRATION_PATH = os.path.join(os.path.dirname(__file__), "calibration.json")

# Valid output range per feature — corrected values are clamped to these.
FEATURE_RANGES = {
    "energy": (0.0, 1.0),
    "valence": (0.0, 1.0),
    "acousticness": (0.0, 1.0),
    "instrumentalness": (0.0, 1.0),
    "loudness": (-60.0, 0.0),
}

_cache: dict | None = None


def load_calibration(refresh: bool = False) -> dict:
    """Return the ``{feature: {slope, intercept, ...}}`` correction map.

    Reads ``calibration.json`` once and caches it. Missing file -> ``{}``.
    """
    global _cache
    if _cache is not None and not refresh:
        return _cache

    profile: dict = {}
    try:
        with open(CALIBRATION_PATH, encoding="utf-8") as handle:
            profile = (json.load(handle) or {}).get("corrections", {}) or {}
    except FileNotFoundError:
        pass
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Ignoring unreadable calibration profile: %s", exc)

    _cache = profile
    return profile


def calibrate(feature: str, value):
    """Apply the fitted correction for ``feature`` and clamp to its range.

    No-op (returns ``value`` unchanged) when no correction is registered.
    """
    if value is None:
        return value

    correction = load_calibration().get(feature)
    if not correction:
        return value

    adjusted = correction["slope"] * value + correction["intercept"]

    lo, hi = FEATURE_RANGES.get(feature, (None, None))
    if lo is not None:
        adjusted = max(lo, min(hi, adjusted))
    return adjusted


def save_calibration(corrections: dict, meta: dict | None = None) -> None:
    """Write a freshly fitted profile to ``calibration.json``."""
    payload = {"meta": meta or {}, "corrections": corrections}
    with open(CALIBRATION_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    load_calibration(refresh=True)
    logger.info("Wrote calibration profile to %s", CALIBRATION_PATH)
