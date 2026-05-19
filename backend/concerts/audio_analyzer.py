"""AI Audio Analysis Engine — extract REAL audio features from actual songs.

Downloads a song's audio stream from JioSaavn, runs it through librosa
to measure genuine spectral and rhythmic properties, then maps those
measurements to the fields the recommendation engine scores on.

This replaces heuristic guesswork with real signal-processing data:
  - energy       → RMS power of the waveform
  - valence      → spectral brightness + mode (major/minor key detection)
  - tempo/BPM    → librosa beat tracking
  - acousticness → ratio of low-frequency spectral energy
  - instrumentalness → vocal frequency band power analysis
  - loudness     → RMS dB (integrated loudness)
  - key/mode     → chroma feature analysis (pitch class detection)

Requires: librosa, numpy, soundfile (via libsndfile1 system package).
All already in requirements.txt / Dockerfile.
"""
from __future__ import annotations

import io
import logging
import os
import re
import tempfile
from pathlib import Path

import numpy as np
import requests
from django.db import transaction

logger = logging.getLogger(__name__)

# How many seconds of audio to analyze. Full tracks are typically 3-5 min;
# analyzing the middle 60s captures the chorus (most representative section)
# while keeping processing fast.
ANALYSIS_DURATION_SEC = 60

# JioSaavn headers (same as playlists/views.py)
_SAAVN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.jiosaavn.com/",
}

# DES key for JioSaavn URL decryption
_DES_KEY = b"38346591"

# Key signature names by pitch class index (0=C, 1=C#, ... 11=B)
_KEY_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Mood derivation thresholds — same as tracks/services.py MOOD_SIGNATURES
_MOOD_SIGNATURES = {
    "celebratory": {"energy_min": 0.75, "valence_min": 0.7},
    "energized": {"energy_min": 0.72, "valence_min": 0.45},
    "calm": {"energy_max": 0.42, "valence_min": 0.4},
    "melancholic": {"energy_max": 0.38, "valence_max": 0.38},
    "anxious": {"energy_min": 0.45, "valence_max": 0.35},
}


class AudioAnalysisError(RuntimeError):
    """Raised when audio analysis fails."""


def _decrypt_saavn_url(encrypted_url: str) -> str:
    """Decrypt JioSaavn's DES-ECB encrypted media URL."""
    import base64
    try:
        from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
    except ImportError:
        from cryptography.hazmat.primitives.ciphers.algorithms import TripleDES
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers import Cipher, modes

    enc_bytes = base64.b64decode(encrypted_url)
    cipher = Cipher(TripleDES(_DES_KEY * 3), modes.ECB(), backend=default_backend())
    dec = cipher.decryptor()
    result = dec.update(enc_bytes) + dec.finalize()
    pad_len = result[-1] if 1 <= result[-1] <= 8 else 0
    return result[: len(result) - pad_len].decode("utf-8").strip()


def _resolve_stream_url(title: str, artist_name: str) -> str:
    """Search JioSaavn for a song and return its decrypted stream URL."""
    query = f"{title} {artist_name}".strip()
    if not query:
        raise AudioAnalysisError("Cannot resolve stream URL: no title/artist")

    response = requests.get(
        "https://www.jiosaavn.com/api.php",
        params={
            "__call": "search.getResults",
            "q": query,
            "p": 1,
            "n": 5,
            "q_format": "1",
            "_format": "json",
            "_marker": "0",
        },
        headers=_SAAVN_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    results = (response.json() or {}).get("results") or []

    if not results:
        raise AudioAnalysisError(f"No JioSaavn results for: {query}")

    # Pick best match by title similarity
    target_words = set(re.sub(r"[^\w\s]", "", title.lower()).split())
    best = results[0]
    best_score = 0.0
    for r in results:
        song_title = r.get("song") or r.get("title") or ""
        words = set(re.sub(r"[^\w\s]", "", song_title.lower()).split())
        if not words or not target_words:
            continue
        overlap = len(target_words & words) / max(len(target_words), len(words))
        if overlap > best_score:
            best_score = overlap
            best = r

    encrypted_url = best.get("encrypted_media_url")
    if not encrypted_url:
        raise AudioAnalysisError("JioSaavn result has no encrypted media URL")

    audio_url = _decrypt_saavn_url(encrypted_url)
    # Upgrade to 320kbps if available
    if best.get("320kbps") == "true":
        audio_url = audio_url.replace("_96.mp4", "_320.mp4").replace(
            "_160.mp4", "_320.mp4"
        )

    return audio_url


def _download_audio(url: str) -> bytes:
    """Download audio from a URL and return raw bytes."""
    response = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
        timeout=30,
        stream=True,
    )
    response.raise_for_status()

    chunks = []
    total = 0
    max_bytes = 15 * 1024 * 1024  # 15 MB max
    for chunk in response.iter_content(chunk_size=65536):
        chunks.append(chunk)
        total += len(chunk)
        if total > max_bytes:
            break

    return b"".join(chunks)


def analyze_audio_bytes(audio_bytes: bytes) -> dict:
    """Run librosa analysis on raw audio bytes and return real features.

    Returns dict with: energy, valence, tempoBpm, acousticness,
    instrumentalness, loudness, keySignature, primaryMood, key, mode.
    """
    import librosa
    import soundfile as sf

    # Write to temp file — librosa needs a file path or file-like object
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        # Load audio — mono, native sample rate
        y, sr = librosa.load(tmp_path, sr=None, mono=True)
        if y is None or len(y) == 0:
            raise AudioAnalysisError("librosa loaded empty audio")

        duration = librosa.get_duration(y=y, sr=sr)

        # Analyze the middle section (most representative — usually chorus)
        if duration > ANALYSIS_DURATION_SEC + 10:
            start = max(0, int((duration - ANALYSIS_DURATION_SEC) / 2))
            start_sample = start * sr
            end_sample = start_sample + ANALYSIS_DURATION_SEC * sr
            y = y[int(start_sample) : int(end_sample)]

        # ── 1. Energy (RMS power, normalized to 0-1) ───────────────────
        rms = librosa.feature.rms(y=y)[0]
        rms_mean = float(np.mean(rms))
        # Normalize: typical RMS for music is 0.01-0.3; map to 0-1
        energy = float(np.clip(rms_mean / 0.20, 0.0, 1.0))

        # ── 2. Tempo / BPM ─────────────────────────────────────────────
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo_bpm = int(round(float(np.atleast_1d(tempo)[0])))
        tempo_bpm = max(40, min(220, tempo_bpm))

        # ── 3. Key signature (chroma analysis) ─────────────────────────
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_mean = np.mean(chroma, axis=1)
        key_idx = int(np.argmax(chroma_mean))
        key_name = _KEY_NAMES[key_idx]

        # Mode detection (major vs minor) via chroma correlation
        # Major: root + major 3rd (4 semitones) + perfect 5th (7 semitones)
        # Minor: root + minor 3rd (3 semitones) + perfect 5th (7 semitones)
        major_score = (
            chroma_mean[key_idx]
            + chroma_mean[(key_idx + 4) % 12]
            + chroma_mean[(key_idx + 7) % 12]
        )
        minor_score = (
            chroma_mean[key_idx]
            + chroma_mean[(key_idx + 3) % 12]
            + chroma_mean[(key_idx + 7) % 12]
        )
        is_major = major_score >= minor_score
        mode = 1 if is_major else 0
        key_signature = f"{key_name} {'major' if is_major else 'minor'}"

        # ── 4. Valence (musical positivity) ────────────────────────────
        # Approximated from: mode (major=happier), spectral brightness,
        # and tempo (faster=more positive).
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        brightness = float(np.mean(spectral_centroid)) / (sr / 2)  # normalize
        brightness = float(np.clip(brightness, 0.0, 1.0))

        tempo_factor = float(np.clip((tempo_bpm - 60) / 140, 0.0, 1.0))
        mode_factor = 0.6 if is_major else 0.35

        # Weighted combination
        valence = float(np.clip(
            0.35 * mode_factor + 0.35 * brightness + 0.30 * tempo_factor,
            0.0,
            1.0,
        ))

        # ── 5. Acousticness ────────────────────────────────────────────
        # Ratio of spectral energy below 2kHz — acoustic instruments
        # concentrate energy in lower frequencies.
        spec = np.abs(librosa.stft(y))
        freq_bins = librosa.fft_frequencies(sr=sr)
        low_mask = freq_bins < 2000
        low_energy = float(np.sum(spec[low_mask, :] ** 2))
        total_energy = float(np.sum(spec ** 2))
        acousticness = float(np.clip(low_energy / max(total_energy, 1e-10), 0.0, 1.0))

        # ── 6. Instrumentalness ────────────────────────────────────────
        # Vocal frequencies are ~85-3000 Hz. If spectral energy in
        # 300-3000 Hz (vocal formant range) is low relative to the rest,
        # the track is likely instrumental.
        vocal_mask = (freq_bins >= 300) & (freq_bins <= 3000)
        vocal_energy = float(np.sum(spec[vocal_mask, :] ** 2))
        vocal_ratio = vocal_energy / max(total_energy, 1e-10)
        # Invert: high vocal ratio → low instrumentalness
        instrumentalness = float(np.clip(1.0 - (vocal_ratio * 2.5), 0.0, 1.0))

        # ── 7. Loudness (dB) ──────────────────────────────────────────
        # Convert RMS to dB scale, normalize to typical music range
        if rms_mean > 0:
            loudness_db = float(20 * np.log10(rms_mean))
        else:
            loudness_db = -60.0
        loudness = float(np.clip(loudness_db, -60.0, 0.0))

        # ── 8. Primary Mood ────────────────────────────────────────────
        primary_mood = _derive_mood(energy, valence)

        return {
            "energy": round(energy, 4),
            "valence": round(valence, 4),
            "tempoBpm": tempo_bpm,
            "acousticness": round(acousticness, 4),
            "instrumentalness": round(instrumentalness, 4),
            "loudness": round(loudness, 1),
            "keySignature": key_signature,
            "primaryMood": primary_mood,
            "key": key_idx,
            "mode": mode,
            "durationSec": round(duration, 1),
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _derive_mood(energy: float, valence: float) -> str:
    """Map energy+valence to a mood label (same logic as tracks/services.py)."""
    if (
        energy >= _MOOD_SIGNATURES["celebratory"]["energy_min"]
        and valence >= _MOOD_SIGNATURES["celebratory"]["valence_min"]
    ):
        return "celebratory"
    if (
        energy >= _MOOD_SIGNATURES["energized"]["energy_min"]
        and valence >= _MOOD_SIGNATURES["energized"]["valence_min"]
    ):
        return "energized"
    if (
        energy <= _MOOD_SIGNATURES["melancholic"]["energy_max"]
        and valence <= _MOOD_SIGNATURES["melancholic"]["valence_max"]
    ):
        return "melancholic"
    if (
        energy >= _MOOD_SIGNATURES["anxious"]["energy_min"]
        and valence <= _MOOD_SIGNATURES["anxious"]["valence_max"]
    ):
        return "anxious"
    if (
        energy <= _MOOD_SIGNATURES["calm"]["energy_max"]
        and valence >= _MOOD_SIGNATURES["calm"]["valence_min"]
    ):
        return "calm"
    return "focused"


def analyze_track(track, *, force: bool = False) -> dict | None:
    """Analyze a Track instance: download its audio and extract real features.

    Returns the feature dict on success, None on failure.
    If force=False, skips tracks that already have audio features.
    """
    if not force and all([
        track.energy is not None,
        track.valence is not None,
        track.tempoBpm is not None,
    ]):
        return None  # Already analyzed

    artist_name = ""
    if track.artistId_id:
        artist_name = getattr(track.artistId, "name", "") or ""

    title = track.title or ""
    if not title:
        logger.warning("Track %s has no title, skipping analysis", track.id)
        return None

    try:
        # Step 1: Get stream URL (use cached if available)
        if track.streamUrl:
            audio_url = track.streamUrl
        else:
            audio_url = _resolve_stream_url(title, artist_name)

        # Step 2: Download audio
        logger.info("Downloading: %s — %s", title, artist_name)
        audio_bytes = _download_audio(audio_url)

        if len(audio_bytes) < 10000:
            logger.warning("Audio too small (%d bytes) for: %s", len(audio_bytes), title)
            return None

        # Step 3: Analyze with librosa
        logger.info("Analyzing: %s (%.1f KB)", title, len(audio_bytes) / 1024)
        features = analyze_audio_bytes(audio_bytes)

        # Step 4: Save to database
        update_fields = []
        field_map = {
            "energy": features["energy"],
            "valence": features["valence"],
            "tempoBpm": features["tempoBpm"],
            "acousticness": features["acousticness"],
            "instrumentalness": features["instrumentalness"],
            "loudness": features["loudness"],
            "keySignature": features["keySignature"],
            "primaryMood": features["primaryMood"],
        }

        for field, value in field_map.items():
            if value is not None:
                setattr(track, field, value)
                update_fields.append(field)

        # Cache the stream URL for future playback
        if not track.streamUrl and audio_url:
            track.streamUrl = audio_url
            update_fields.append("streamUrl")

        # Mark instrumentalness-derived fields
        if features["instrumentalness"] >= 0.6:
            track.isInstrumental = True
            update_fields.append("isInstrumental")

        if update_fields:
            track.save(update_fields=update_fields)
            logger.info(
                "✓ %s — energy=%.2f valence=%.2f tempo=%d mood=%s key=%s",
                title,
                features["energy"],
                features["valence"],
                features["tempoBpm"],
                features["primaryMood"],
                features["keySignature"],
            )

        return features

    except AudioAnalysisError as exc:
        logger.warning("Analysis failed for '%s': %s", title, exc)
        return None
    except Exception as exc:
        logger.error("Unexpected error analyzing '%s': %s", title, exc, exc_info=True)
        return None
