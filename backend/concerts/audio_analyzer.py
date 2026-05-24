"""Backward-compatibility shim.

The audio analysis engine now lives in the dedicated :mod:`tracks.analysis`
package. This module is kept only so existing imports
(``from concerts.audio_analyzer import analyze_track``) keep working.

New code should import from ``tracks.analysis`` directly.
"""
from tracks.analysis import (  # noqa: F401
    AudioAnalysisError,
    analyze_audio_bytes,
    analyze_track,
)

__all__ = ["analyze_track", "analyze_audio_bytes", "AudioAnalysisError"]
