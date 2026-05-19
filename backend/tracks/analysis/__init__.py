"""Harmonic Navigator — in-house audio analysis engine.

This package is *our own* feature-extraction engine. It depends on no
third-party feature API (no Spotify Audio Features, no AcousticBrainz) and
no labelled dataset. Given a song's audio it measures everything itself:

    audio bytes
        -> dsp.extract_features()      raw signal measurements
        -> extractors.*()              deterministic Track features
        -> classifiers.*()             valence / mood / genre / region

Layers
------
* ``audio_source``  fetch audio bytes (JioSaavn stream -> bytes)
* ``dsp``           pure signal processing -> a flat ``FeatureVector``
* ``extractors``    map measurements -> energy, acousticness, etc.
* ``classifiers``   judgement calls (valence, mood, genre, region) behind
                    a pluggable interface — heuristic today, ML-ready.
* ``engine``        orchestration + persistence to the ``Track`` model.

Public API kept stable for callers (and for ``concerts.audio_analyzer``,
which is now a thin shim over this package).
"""
from .audio_source import AudioAnalysisError
from .engine import analyze_audio_bytes, analyze_track

__all__ = ["analyze_track", "analyze_audio_bytes", "AudioAnalysisError"]
