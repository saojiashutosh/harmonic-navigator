from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .excel_storage import sync_track_to_excel
from .models import Artist, AudioFeatureSnapshot, Track
from .spotify_client import search_tracks


MOOD_SIGNATURES = {
    "celebratory": {"energy_min": 0.75, "valence_min": 0.7},
    "energized": {"energy_min": 0.72, "valence_min": 0.45},
    "calm": {"energy_max": 0.42, "valence_min": 0.4},
    "melancholic": {"energy_max": 0.38, "valence_max": 0.38},
    "anxious": {"energy_min": 0.45, "valence_max": 0.35},
}

KEY_SIGNATURES = {
    0: "C",
    1: "C#",
    2: "D",
    3: "D#",
    4: "E",
    5: "F",
    6: "F#",
    7: "G",
    8: "G#",
    9: "A",
    10: "A#",
    11: "B",
}


def import_spotify_search_results(
    query: str,
    limit: int = 20,
    market: str | None = None,
    metadata: dict | None = None,
) -> list[Track]:
    payloads = search_tracks(query=query, limit=limit, market=market)
    return [import_spotify_track(payload, metadata=metadata) for payload in payloads]


def import_spotify_track(payload: dict, metadata: dict | None = None) -> Track:
    artist_payload = payload["artist"]
    audio_features = payload.get("audio_features") or {}
    metadata = metadata or {}

    with transaction.atomic():
        artist = _upsert_artist(artist_payload)

        defaults = {
            "title": payload.get("title"),
            "artistId": artist,
            "source": Track.SourceChoices.SPOTIFY,
            "previewUrl": payload.get("preview_url"),
            "externalUrl": payload.get("external_url"),
            "durationMs": payload.get("duration_ms"),
            "tempoBpm": _round_positive(audio_features.get("tempo")),
            "keySignature": _build_key_signature(audio_features),
            "energy": audio_features.get("energy"),
            "valence": audio_features.get("valence"),
            "acousticness": audio_features.get("acousticness"),
            "instrumentalness": audio_features.get("instrumentalness"),
            "loudness": audio_features.get("loudness"),
            "isExplicit": payload.get("is_explicit", False),
            "isInstrumental": derive_is_instrumental(audio_features),
            "type": derive_track_type(audio_features),
            "primaryMood": derive_primary_mood(audio_features),
            "language": metadata.get("language"),
            "genre": metadata.get("genre"),
            "region": metadata.get("region"),
            "artistPopularity": metadata.get("artistPopularity"),
            "ragaName": metadata.get("ragaName"),
            "classicalForm": metadata.get("classicalForm"),
            "isActive": True,
            "featuresSyncedAt": timezone.now() if audio_features else None,
        }

        track, _ = Track.objects.update_or_create(
            spotifyId=payload["spotify_id"],
            defaults=defaults,
        )

        if audio_features:
            AudioFeatureSnapshot.objects.create(
                trackId=track,
                snapshot=audio_features,
            )

        transaction.on_commit(lambda: sync_track_to_excel(track))

    return track


def derive_is_instrumental(audio_features: dict) -> bool:
    instrumentalness = audio_features.get("instrumentalness")
    return instrumentalness is not None and instrumentalness >= 0.6


def derive_track_type(audio_features: dict) -> str:
    instrumentalness = audio_features.get("instrumentalness")
    energy = audio_features.get("energy")
    acousticness = audio_features.get("acousticness")

    if instrumentalness is not None and instrumentalness >= 0.75:
        return Track.TypeChoices.INSTRUMENTAL
    if (
        energy is not None
        and energy <= 0.25
        and acousticness is not None
        and acousticness >= 0.5
    ):
        return Track.TypeChoices.AMBIENT
    if instrumentalness is not None and instrumentalness >= 0.6:
        return Track.TypeChoices.INSTRUMENTAL
    return Track.TypeChoices.SONG


def derive_primary_mood(audio_features: dict) -> str:
    energy = audio_features.get("energy")
    valence = audio_features.get("valence")

    if energy is None or valence is None:
        return "focused"
    if energy >= MOOD_SIGNATURES["celebratory"]["energy_min"] and valence >= MOOD_SIGNATURES["celebratory"]["valence_min"]:
        return "celebratory"
    if energy >= MOOD_SIGNATURES["energized"]["energy_min"] and valence >= MOOD_SIGNATURES["energized"]["valence_min"]:
        return "energized"
    if energy <= MOOD_SIGNATURES["melancholic"]["energy_max"] and valence <= MOOD_SIGNATURES["melancholic"]["valence_max"]:
        return "melancholic"
    if energy >= MOOD_SIGNATURES["anxious"]["energy_min"] and valence <= MOOD_SIGNATURES["anxious"]["valence_max"]:
        return "anxious"
    if energy <= MOOD_SIGNATURES["calm"]["energy_max"] and valence >= MOOD_SIGNATURES["calm"]["valence_min"]:
        return "calm"
    return "focused"


def _upsert_artist(payload: dict) -> Artist:
    spotify_id = payload.get("spotify_id")
    defaults = {"name": payload.get("name"), "spotifyId": spotify_id}
    if spotify_id:
        artist, _ = Artist.objects.update_or_create(
            spotifyId=spotify_id,
            defaults=defaults,
        )
        return artist
    artist, _ = Artist.objects.get_or_create(
        name=payload.get("name"),
        defaults=defaults,
    )
    return artist


def _round_positive(value: float | None) -> int | None:
    if value is None:
        return None
    rounded = round(value)
    return rounded if rounded > 0 else None


def _build_key_signature(audio_features: dict) -> str | None:
    key = audio_features.get("key")
    mode = audio_features.get("mode")
    if key is None or key not in KEY_SIGNATURES:
        return None
    suffix = " major" if mode == 1 else " minor" if mode == 0 else ""
    return f"{KEY_SIGNATURES[key]}{suffix}"
