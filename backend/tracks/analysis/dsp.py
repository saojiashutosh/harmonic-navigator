"""Signal-processing layer — the engine's measurement instrument.

Everything here is pure DSP on the raw waveform (librosa + numpy). No
network, no datasets, no models. The output is a ``FeatureVector``: a flat
bundle of numeric descriptors that every downstream extractor and
classifier consumes.

That flat vector is also the engine's *ML-ready contract*. Heuristic
classifiers read named fields off it today; a trained model would consume
the very same vector via :meth:`FeatureVector.as_array`, so swapping in a
model never requires touching this file.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field

import numpy as np

from .audio_source import AudioAnalysisError

logger = logging.getLogger(__name__)

# Multi-window analysis: sample N evenly-spread windows of WINDOW_SEC each
# and aggregate the per-window features. This removes the section-sampling
# bias of looking at only one chunk (e.g. landing on a pad-only verse of an
# EDM track and reading it as 'acoustic'). Medians across windows are robust
# to a single weird section.
WINDOW_SEC = 30
N_WINDOWS = 3
# librosa default onset hop length — used by tempo octave correction below.
HOP_LENGTH = 512

# Decode everything to this sample rate. 22.05 kHz keeps all musically
# relevant content (Nyquist ~11 kHz) while roughly halving the work versus
# 44.1 kHz — the standard rate for music information retrieval.
TARGET_SR = 22050

# Pitch-class names, index 0 = C.
KEY_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Schmuckler key profiles — perceived tonal weight of each scale
# degree. Correlating a song's chroma against the 24 rotations of these
# gives key + mode with zero training data (a classic music-theory method).
_MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
_MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)


@dataclass
class FeatureVector:
    """Flat numeric descriptors of one audio segment.

    All fields are plain floats/ints (or 12/13-length lists) so the whole
    object is JSON-serialisable and model-friendly. Values are normalised
    to roughly 0-1 unless noted, so heuristics and models can treat them
    uniformly.
    """

    # --- loudness & dynamics -------------------------------------------
    rms_mean: float          # average signal power (raw RMS, ~0-0.4)
    rms_std: float           # variability of power over time
    dynamic_range: float     # 0-1, spread between quiet and loud moments
    loudness_db: float       # integrated loudness, dB (-60..0)

    # --- spectral / timbre ---------------------------------------------
    brightness: float        # spectral centroid, 0-1 (dark -> bright)
    spectral_rolloff: float  # 0-1, frequency below which 85% energy sits
    spectral_bandwidth: float  # 0-1, spectral spread
    spectral_flatness: float   # 0-1, tonal -> noisy/synthetic
    spectral_contrast: float   # 0-1, peak-to-valley spectral definition
    zero_crossing_rate: float  # 0-1, noisiness / percussiveness

    # --- rhythm --------------------------------------------------------
    tempo_bpm: int           # beats per minute
    beat_strength: float     # 0-1, how punchy the onsets are
    onset_rate: float        # note onsets per second
    pulse_clarity: float     # 0-1, how steady/periodic the pulse is

    # --- harmony / source balance -------------------------------------
    harmonic_ratio: float    # 0-1, harmonic energy / total
    percussive_ratio: float  # 0-1, percussive energy / total
    low_freq_ratio: float    # 0-1, energy below 2 kHz / total
    vocal_band_ratio: float  # 0-1, energy 300-3000 Hz / total

    # --- tonality ------------------------------------------------------
    key: int                 # 0-11 pitch class of the tonic
    mode: int                # 1 = major, 0 = minor
    key_strength: float      # 0-1, confidence of the key estimate
    chroma: list = field(default_factory=list)  # 12-d pitch-class profile
    mfcc: list = field(default_factory=list)     # 13-d timbre fingerprint

    # --- meta ----------------------------------------------------------
    duration_sec: float = 0.0
    sample_rate: int = 0

    # numeric-only fields, in a fixed order — the model feature order.
    _SCALAR_KEYS = (
        "rms_mean", "rms_std", "dynamic_range", "loudness_db",
        "brightness", "spectral_rolloff", "spectral_bandwidth",
        "spectral_flatness", "spectral_contrast", "zero_crossing_rate",
        "tempo_bpm", "beat_strength", "onset_rate", "pulse_clarity",
        "harmonic_ratio", "percussive_ratio", "low_freq_ratio",
        "vocal_band_ratio", "key", "mode", "key_strength",
    )

    def as_dict(self) -> dict:
        """JSON-safe dict of every field (stored in AudioFeatureSnapshot)."""
        return asdict(self)

    def as_feature_map(self) -> dict:
        """Flat ``{name: float}`` map — the input every classifier reads."""
        data = {k: float(getattr(self, k)) for k in self._SCALAR_KEYS}
        for i, value in enumerate(self.chroma):
            data[f"chroma_{i}"] = float(value)
        return data

    def as_array(self) -> np.ndarray:
        """Fixed-order numeric vector — the input a trained model would use."""
        scalars = [float(getattr(self, k)) for k in self._SCALAR_KEYS]
        return np.array(scalars + list(self.chroma) + list(self.mfcc), dtype=float)


def _norm(value: float, lo: float, hi: float) -> float:
    """Linear-scale ``value`` from [lo, hi] into [0, 1] and clamp."""
    if hi <= lo:
        return 0.0
    return float(np.clip((value - lo) / (hi - lo), 0.0, 1.0))


def _detect_key(chroma_mean: np.ndarray) -> tuple[int, int, float]:
    """Krumhansl-Schmuckler key finding. Returns ``(key, mode, strength)``."""
    chroma_centered = chroma_mean - chroma_mean.mean()
    major = _MAJOR_PROFILE - _MAJOR_PROFILE.mean()
    minor = _MINOR_PROFILE - _MINOR_PROFILE.mean()

    best_score, best_key, best_mode = -2.0, 0, 1
    for tonic in range(12):
        # Rotate the chroma so the candidate tonic sits at index 0.
        rotated = np.roll(chroma_centered, -tonic)
        major_corr = float(np.corrcoef(rotated, major)[0, 1])
        minor_corr = float(np.corrcoef(rotated, minor)[0, 1])
        if major_corr > best_score:
            best_score, best_key, best_mode = major_corr, tonic, 1
        if minor_corr > best_score:
            best_score, best_key, best_mode = minor_corr, tonic, 0

    if np.isnan(best_score):
        return 0, 1, 0.0
    return best_key, best_mode, float(np.clip(best_score, 0.0, 1.0))


def _probe_duration(path: str) -> float:
    """Return a media file's duration in seconds via ffprobe (0.0 if unknown)."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def load_audio(audio_bytes: bytes) -> tuple[np.ndarray, int, float]:
    """Decode audio bytes and return ``(waveform, sample_rate, full_duration)``.

    Decoding is done directly with ffmpeg: JioSaavn serves AAC/.mp4, which
    libsndfile cannot read, and librosa's ``audioread`` fallback decodes
    the whole file painfully slowly. We ask ffmpeg to render the entire
    track to a 22.05 kHz mono WAV, which librosa then loads instantly.
    Multi-window carving happens in :func:`extract_features` so the
    ffmpeg pass runs once per song, not once per window.
    """
    import librosa

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(audio_bytes)
        src_path = tmp.name
    wav_path = src_path + ".wav"

    try:
        full_duration = _probe_duration(src_path)

        # Decode the whole track once; multi-window carving happens in
        # extract_features so we don't re-run ffmpeg per window.
        cmd = ["ffmpeg", "-y", "-loglevel", "error",
               "-i", src_path, "-ac", "1", "-ar", str(TARGET_SR), wav_path]

        try:
            subprocess.run(cmd, capture_output=True, timeout=180, check=True)
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or b"").decode(errors="ignore")[:200]
            raise AudioAnalysisError(f"ffmpeg could not decode audio: {detail}")
        except subprocess.TimeoutExpired:
            raise AudioAnalysisError("ffmpeg decode timed out")

        waveform, sample_rate = librosa.load(wav_path, sr=None, mono=True)
    finally:
        for path in (src_path, wav_path):
            try:
                os.unlink(path)
            except OSError:
                pass

    if waveform is None or len(waveform) == 0:
        raise AudioAnalysisError("Decoder produced empty audio")

    # ffmpeg already extracted the window; fall back to the segment length
    # only when ffprobe could not report a duration.
    if full_duration <= 0:
        full_duration = float(len(waveform) / sample_rate)

    return waveform, sample_rate, full_duration


def _octave_correct_tempo(raw_bpm: int, onset_env: np.ndarray,
                          sr: int, hop_length: int = HOP_LENGTH) -> int:
    """Pick the most plausible octave-equivalent of ``raw_bpm``.

    ``librosa.beat.beat_track`` sometimes locks onto a half- or double-time
    beat — e.g. a 165 BPM dance track reads as 83. We score the candidate
    × ½ / 1 / 2 by its onset-autocorrelation support and give a small
    bonus to the musically common 80–160 BPM band, then pick the winner.
    """
    import librosa

    candidates = []
    for factor in (0.5, 1.0, 2.0):
        bpm = raw_bpm * factor
        if 40 <= bpm <= 220:
            candidates.append(bpm)
    if not candidates or len(onset_env) < 16:
        return raw_bpm

    autocorr = librosa.autocorrelate(onset_env)
    if autocorr[0] <= 0:
        return raw_bpm

    scored = []
    for bpm in candidates:
        # Lag (in onset-envelope frames) corresponding to one beat period.
        lag = int(round((60.0 / bpm) * (sr / hop_length)))
        if 1 <= lag < len(autocorr):
            support = float(autocorr[lag] / autocorr[0])
            if 80 <= bpm <= 160:
                support *= 1.15
            scored.append((bpm, support))
    if not scored:
        return raw_bpm
    best_bpm, _ = max(scored, key=lambda x: x[1])
    return int(round(best_bpm))


def _carve_windows(y_full: np.ndarray, sr: int, full_duration: float,
                   n: int = N_WINDOWS, window_sec: float = WINDOW_SEC
                   ) -> list[np.ndarray]:
    """Carve ``n`` evenly-spread analysis windows out of the full waveform.

    Each window is centred at the (k+½)/n fraction of the track, so for
    n=3 we sample roughly the 1/6, 1/2, 5/6 marks. Short tracks fall back
    to a single full-track window.
    """
    total = len(y_full)
    if full_duration <= window_sec * 1.1:
        return [y_full]

    window_samples = int(window_sec * sr)
    windows: list[np.ndarray] = []
    for k in range(n):
        frac = (k + 0.5) / n
        centre = int(frac * total)
        start = max(0, centre - window_samples // 2)
        end = min(total, start + window_samples)
        start = max(0, end - window_samples)  # tighten if we ran off the end
        windows.append(y_full[start:end])
    return windows


def _compute_segment_features(y: np.ndarray, sr: int) -> dict:
    """Run the DSP pass for one analysis window and return a flat dict.

    Returns scalar features plus the raw chroma_mean / mfcc_mean arrays so
    the aggregator can re-derive the song-level key from averaged chroma
    instead of voting over per-window keys.
    """
    import librosa

    # --- loudness & dynamics ------------------------------------------
    rms = librosa.feature.rms(y=y)[0]
    rms_mean = float(np.mean(rms))
    rms_std = float(np.std(rms))
    rms_db = 20.0 * np.log10(np.maximum(rms, 1e-7))
    dynamic_range = _norm(
        float(np.percentile(rms_db, 95) - np.percentile(rms_db, 5)), 0.0, 45.0
    )
    loudness_db = float(np.clip(20.0 * np.log10(max(rms_mean, 1e-7)), -60.0, 0.0))

    # --- spectral / timbre --------------------------------------------
    centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr)))
    bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)))
    flatness_raw = float(np.mean(librosa.feature.spectral_flatness(y=y)))
    contrast_raw = float(np.mean(librosa.feature.spectral_contrast(y=y, sr=sr)))
    zcr_raw = float(np.mean(librosa.feature.zero_crossing_rate(y=y)))

    brightness = _norm(centroid, 500.0, 4000.0)
    spectral_rolloff = _norm(rolloff, 1000.0, 8000.0)
    spectral_bandwidth = _norm(bandwidth, 500.0, 4000.0)
    spectral_contrast = _norm(contrast_raw, 10.0, 35.0)
    spectral_flatness = _norm(flatness_raw, 0.0, 0.15)
    zero_crossing_rate = _norm(zcr_raw, 0.0, 0.25)

    # --- rhythm --------------------------------------------------------
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, _ = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
    raw_tempo = int(round(float(np.atleast_1d(tempo)[0])))
    tempo_bpm = _octave_correct_tempo(raw_tempo, onset_env, sr)
    tempo_bpm = max(40, min(220, tempo_bpm))

    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    segment_dur = max(len(y) / sr, 1e-6)
    onset_rate = float(len(onsets) / segment_dur)
    beat_strength = _norm(float(np.percentile(onset_env, 90)), 0.0, 6.0)

    autocorr = librosa.autocorrelate(onset_env - onset_env.mean())
    if len(autocorr) > 4 and autocorr[0] > 0:
        pulse_clarity = _norm(float(np.max(autocorr[2:]) / autocorr[0]), 0.0, 1.0)
    else:
        pulse_clarity = 0.0

    # --- harmonic / percussive split ----------------------------------
    y_harmonic, y_percussive = librosa.effects.hpss(y)
    harm_energy = float(np.sum(y_harmonic ** 2))
    perc_energy = float(np.sum(y_percussive ** 2))
    total_hp = harm_energy + perc_energy + 1e-10
    harmonic_ratio = harm_energy / total_hp
    percussive_ratio = perc_energy / total_hp

    # --- frequency-band energy balance --------------------------------
    spectrum = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)
    power = spectrum ** 2
    total_power = float(np.sum(power)) + 1e-10
    low_freq_ratio = float(np.sum(power[freqs < 2000, :]) / total_power)
    vocal_mask = (freqs >= 300) & (freqs <= 3000)
    vocal_band_ratio = float(np.sum(power[vocal_mask, :]) / total_power)

    # --- chroma & mfcc (kept as arrays for cross-window averaging) ----
    chroma_mean = np.mean(librosa.feature.chroma_cqt(y=y, sr=sr), axis=1)
    mfcc_mean = np.mean(librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13), axis=1)

    return {
        "rms_mean": rms_mean, "rms_std": rms_std,
        "dynamic_range": dynamic_range, "loudness_db": loudness_db,
        "brightness": brightness, "spectral_rolloff": spectral_rolloff,
        "spectral_bandwidth": spectral_bandwidth,
        "spectral_flatness": spectral_flatness,
        "spectral_contrast": spectral_contrast,
        "zero_crossing_rate": zero_crossing_rate,
        "tempo_bpm": tempo_bpm,
        "beat_strength": beat_strength, "onset_rate": onset_rate,
        "pulse_clarity": pulse_clarity,
        "harmonic_ratio": harmonic_ratio,
        "percussive_ratio": percussive_ratio,
        "low_freq_ratio": low_freq_ratio,
        "vocal_band_ratio": vocal_band_ratio,
        "chroma_mean": chroma_mean,
        "mfcc_mean": mfcc_mean,
    }


def _aggregate_segments(segments: list[dict], sr: int,
                        full_duration: float) -> FeatureVector:
    """Combine per-segment features into one FeatureVector.

    **Median** across segments for scalars (robust to a single odd
    window), **average** the chroma vectors and re-run Krumhansl on the
    result (one canonical key per song), and **average** the MFCC
    fingerprints.
    """
    def med(key: str) -> float:
        return float(np.median([s[key] for s in segments]))

    chroma_avg = np.mean([s["chroma_mean"] for s in segments], axis=0)
    mfcc_avg = np.mean([s["mfcc_mean"] for s in segments], axis=0)
    key, mode, key_strength = _detect_key(chroma_avg)
    chroma_norm = (chroma_avg / (chroma_avg.sum() + 1e-10)).tolist()

    tempo_bpm = int(round(float(np.median([s["tempo_bpm"] for s in segments]))))
    tempo_bpm = max(40, min(220, tempo_bpm))

    return FeatureVector(
        rms_mean=round(med("rms_mean"), 6),
        rms_std=round(med("rms_std"), 6),
        dynamic_range=round(med("dynamic_range"), 4),
        loudness_db=round(med("loudness_db"), 2),
        brightness=round(med("brightness"), 4),
        spectral_rolloff=round(med("spectral_rolloff"), 4),
        spectral_bandwidth=round(med("spectral_bandwidth"), 4),
        spectral_flatness=round(med("spectral_flatness"), 4),
        spectral_contrast=round(med("spectral_contrast"), 4),
        zero_crossing_rate=round(med("zero_crossing_rate"), 4),
        tempo_bpm=tempo_bpm,
        beat_strength=round(med("beat_strength"), 4),
        onset_rate=round(med("onset_rate"), 3),
        pulse_clarity=round(med("pulse_clarity"), 4),
        harmonic_ratio=round(med("harmonic_ratio"), 4),
        percussive_ratio=round(med("percussive_ratio"), 4),
        low_freq_ratio=round(med("low_freq_ratio"), 4),
        vocal_band_ratio=round(med("vocal_band_ratio"), 4),
        key=key, mode=mode, key_strength=round(key_strength, 4),
        chroma=[round(c, 4) for c in chroma_norm],
        mfcc=[round(m, 3) for m in mfcc_avg.tolist()],
        duration_sec=round(full_duration, 1),
        sample_rate=sr,
    )


def extract_features(audio_bytes: bytes) -> FeatureVector:
    """Run the multi-window DSP pass and return one aggregated FeatureVector."""
    y_full, sr, full_duration = load_audio(audio_bytes)
    windows = _carve_windows(y_full, sr, full_duration)
    segments = [_compute_segment_features(y, sr) for y in windows]
    return _aggregate_segments(segments, sr, full_duration)
