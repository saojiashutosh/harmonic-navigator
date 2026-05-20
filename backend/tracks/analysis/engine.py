"""Engine orchestration — bytes in, Track features out.

Wires the layers together::

    audio bytes -> dsp.extract_features -> extractors -> classifiers
                -> persisted Track fields + AudioFeatureSnapshot

This is the only module callers need; ``concerts.audio_analyzer`` is a
thin shim over the two public functions defined here.
"""
from __future__ import annotations

import logging

from .audio_source import AudioAnalysisError, fetch_track_audio
from .calibration import calibrate, load_calibration
from .classifiers import get_estimator
from .dsp import extract_features
from .extractors import extract_base_features

logger = logging.getLogger(__name__)

# Track is considered analysed once these core features exist.
_CORE_FIELDS = ("energy", "valence", "tempoBpm")


def analyze_audio_bytes(
    audio_bytes: bytes, *, metadata: dict | None = None, calibrated: bool = True
) -> dict:
    """Analyse raw audio bytes and return a full feature dict.

    ``metadata`` (optional) carries non-audio context — currently
    ``language`` is used by the region classifier. The returned dict is
    JSON-safe and includes the low-level ``featureVector`` for auditing.

    ``calibrated`` applies the fitted calibration profile to the measured
    features. Pass ``calibrated=False`` to get the engine's *raw* output —
    used by the ``calibrate_audio_engine`` command while fitting that
    profile (so corrections are never fitted on top of corrections).
    """
    metadata = metadata or {}

    def _adjust(feature: str, value):
        return calibrate(feature, value) if calibrated else value

    # 1. Measure the signal.
    fv = extract_features(audio_bytes)

    # 2. Deterministic features (direct measurements), calibration-corrected.
    base = extract_base_features(fv)
    energy = round(_adjust("energy", base["energy"]), 4)
    acousticness = round(_adjust("acousticness", base["acousticness"]), 4)
    instrumentalness = round(_adjust("instrumentalness", base["instrumentalness"]), 4)
    loudness = round(_adjust("loudness", base["loudness"]), 1)

    # 3. Build the flat feature map every classifier consumes.
    feature_map = fv.as_feature_map()
    feature_map.update(
        energy=energy,
        acousticness=acousticness,
        instrumentalness=instrumentalness,
        loudness=loudness,
    )

    # 4. Judgement features (heuristic today, ML-swappable).
    valence = round(
        _adjust("valence", get_estimator("valence").predict(feature_map, metadata=metadata)),
        4,
    )
    feature_map["valence"] = valence

    mood = get_estimator("mood").predict(feature_map, metadata=metadata)
    genre = get_estimator("genre").predict(feature_map, metadata=metadata)
    region = get_estimator("region").predict(feature_map, metadata=metadata)

    return {
        "energy": energy,
        "valence": valence,
        "tempoBpm": base["tempoBpm"],
        "acousticness": acousticness,
        "instrumentalness": instrumentalness,
        "loudness": loudness,
        "keySignature": base["keySignature"],
        "key": base["key"],
        "mode": base["mode"],
        "primaryMood": mood.label,
        "moodConfidence": mood.confidence,
        "genre": genre.label,
        "genreConfidence": genre.confidence,
        "region": region.label,
        "regionConfidence": region.confidence,
        "durationSec": fv.duration_sec,
        "calibrated": bool(calibrated and load_calibration()),
        "featureVector": fv.as_dict(),
    }


def analyze_track(track, *, force: bool = False) -> dict | None:
    """Analyse a ``Track``: fetch its audio, extract features, persist them.

    Returns the feature dict on success, ``None`` when skipped or failed.
    With ``force=False`` a track that already has the core features is
    skipped untouched.
    """
    from django.utils import timezone

    from tracks.models import AudioFeatureSnapshot

    if not force and all(getattr(track, f) is not None for f in _CORE_FIELDS):
        return None  # already analysed

    title = (track.title or "").strip()
    if not title:
        logger.warning("Track %s has no title — skipping", track.id)
        return None

    artist_name = ""
    if track.artistId_id:
        artist_name = getattr(track.artistId, "name", "") or ""

    try:
        # 1. Fetch audio (cached stream URL if we have one).
        audio_bytes, audio_url = fetch_track_audio(
            title, artist_name, stream_url=track.streamUrl or ""
        )

        # 2. Run the engine.
        metadata = {
            "language": track.language,
            "artist": artist_name,
            "source": track.source,
            "release_year": track.releaseYear,
        }
        features = analyze_audio_bytes(audio_bytes, metadata=metadata)

        # 3. Persist measured + inferred features.
        update_fields = []
        direct = {
            "energy": features["energy"],
            "valence": features["valence"],
            "tempoBpm": features["tempoBpm"],
            "acousticness": features["acousticness"],
            "instrumentalness": features["instrumentalness"],
            "loudness": features["loudness"],
            "keySignature": features["keySignature"],
            "primaryMood": features["primaryMood"],
        }
        for field_name, value in direct.items():
            setattr(track, field_name, value)
            update_fields.append(field_name)

        # Genre/region may already be set from a metadata import — only
        # fill them when empty (or when explicitly forced).
        if (force or not track.genre) and features["genre"]:
            track.genre = features["genre"]
            update_fields.append("genre")
        if (force or not track.region) and features["region"] != "Unknown":
            track.region = features["region"]
            update_fields.append("region")

        # Cache the resolved stream URL for future playback.
        if not track.streamUrl and audio_url:
            track.streamUrl = audio_url
            update_fields.append("streamUrl")

        if features["instrumentalness"] >= 0.6 and not track.isInstrumental:
            track.isInstrumental = True
            update_fields.append("isInstrumental")

        track.featuresSyncedAt = timezone.now()
        update_fields.append("featuresSyncedAt")

        track.save(update_fields=update_fields)

        # 4. Keep an immutable, auditable snapshot of every run.
        AudioFeatureSnapshot.objects.create(trackId=track, snapshot=features)

        logger.info(
            "Analysed '%s' — energy=%.2f valence=%.2f tempo=%d "
            "mood=%s genre=%s key=%s",
            title, features["energy"], features["valence"],
            features["tempoBpm"], features["primaryMood"],
            features["genre"], features["keySignature"],
        )
        return features

    except AudioAnalysisError as exc:
        logger.warning("Analysis failed for '%s': %s", title, exc)
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Unexpected error analysing '%s': %s", title, exc, exc_info=True)
        return None
