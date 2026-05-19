"""Deterministic feature extractors.

These map raw DSP measurements onto the directly-measurable ``Track``
fields. They are *not* judgement calls — each is a transparent formula
over a :class:`~tracks.analysis.dsp.FeatureVector`, so they stay rule-based
permanently (no ML needed). The judgement features — valence, mood, genre,
region — live in :mod:`tracks.analysis.classifiers` instead.
"""
from __future__ import annotations

import numpy as np

from .dsp import KEY_NAMES, FeatureVector


def _clip01(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def extract_energy(fv: FeatureVector) -> float:
    """Perceived intensity / activity, 0-1.

    Energy is felt as a blend of *how loud*, *how bright*, *how punchy* and
    *how percussion-driven* a track is — EDM and rock score high, a piano
    lullaby scores low. We combine four DSP cues accordingly.
    """
    loudness_cue = _clip01(fv.rms_mean / 0.20)        # average power
    brightness_cue = fv.brightness                    # spectral centroid
    punch_cue = fv.beat_strength                      # onset strength
    drive_cue = fv.percussive_ratio                   # percussion balance

    energy = (
        0.40 * loudness_cue
        + 0.20 * brightness_cue
        + 0.20 * punch_cue
        + 0.20 * drive_cue
    )
    return round(_clip01(energy), 4)


def extract_loudness(fv: FeatureVector) -> float:
    """Integrated loudness in dB (-60..0) — a direct measurement."""
    return round(float(np.clip(fv.loudness_db, -60.0, 0.0)), 1)


def extract_tempo(fv: FeatureVector) -> int:
    """Tempo in BPM, clamped to the Track model's validator range."""
    return max(40, min(220, int(fv.tempo_bpm)))


def extract_acousticness(fv: FeatureVector) -> float:
    """Probability the track is acoustic rather than electronic/produced, 0-1.

    Acoustic recordings are tonal (low spectral flatness), harmonic-rich,
    energy-concentrated in lower frequencies and low in raw noisiness.
    """
    tonal_cue = 1.0 - fv.spectral_flatness        # synthetic timbres flatten
    harmonic_cue = fv.harmonic_ratio              # natural harmonic content
    low_freq_cue = fv.low_freq_ratio              # acoustic energy sits low
    clean_cue = 1.0 - fv.zero_crossing_rate       # less buzzy/distorted

    acousticness = (
        0.35 * tonal_cue
        + 0.30 * harmonic_cue
        + 0.20 * low_freq_cue
        + 0.15 * clean_cue
    )
    return round(_clip01(acousticness), 4)


def extract_instrumentalness(fv: FeatureVector) -> float:
    """Likelihood the track has no lead vocals, 0-1.

    A precise answer needs vocal source separation (Demucs/Spleeter); as a
    fast, self-contained proxy we measure how much energy and tonal
    activity sits in the human vocal band (300-3000 Hz). Strong, tonal
    vocal-band content -> low instrumentalness.
    """
    # Vocal-band energy share, rescaled: ~0.4+ is clearly vocal-driven.
    vocal_presence = _clip01((fv.vocal_band_ratio - 0.10) / 0.35)
    # Sung vocals are tonal; weight presence by how tonal the mix is.
    vocal_presence *= _clip01(0.4 + 0.6 * (1.0 - fv.spectral_flatness))
    return round(_clip01(1.0 - vocal_presence), 4)


def extract_key_signature(fv: FeatureVector) -> str:
    """Human-readable key, e.g. ``"A minor"`` (from Krumhansl key finding)."""
    name = KEY_NAMES[fv.key % 12]
    return f"{name} {'major' if fv.mode == 1 else 'minor'}"


def extract_base_features(fv: FeatureVector) -> dict:
    """Compute every deterministic Track feature from a FeatureVector."""
    return {
        "energy": extract_energy(fv),
        "loudness": extract_loudness(fv),
        "tempoBpm": extract_tempo(fv),
        "acousticness": extract_acousticness(fv),
        "instrumentalness": extract_instrumentalness(fv),
        "keySignature": extract_key_signature(fv),
        "key": fv.key,
        "mode": fv.mode,
    }
