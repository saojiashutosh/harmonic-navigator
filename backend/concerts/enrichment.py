"""Enrichment module — combines REAL audio analysis with heuristic fallback.

Priority order:
1. Real audio analysis (download + librosa) — accurate, but slow (~3s/track)
2. Heuristic estimation from metadata — fast, but approximate

The recommendation engine needs every track to have energy, valence,
primaryMood, genre, and region.  This module ensures those are always set,
using real data when possible and reasonable estimates when not.
"""
from __future__ import annotations

import logging
import re

from tracks.services import derive_primary_mood

logger = logging.getLogger(__name__)


# ── Title-keyword → mood/energy/valence heuristics ──────────────────────
# Used as fallback when audio analysis fails (e.g. stream URL unavailable).
_TITLE_SIGNALS: list[tuple[re.Pattern, dict]] = [
    (re.compile(r"\b(lori|lullaby|cradle|lofi|lo[\s-]?fi|slowed|reverb)\b", re.I),
     {"energy": 0.20, "valence": 0.40, "mood": "calm", "acousticness": 0.75}),
    (re.compile(r"\b(bhajan|aarti|kirtan|mantra|chalisa|stotra|shlok|abhang|vandana|bhakti|qawwali)\b", re.I),
     {"energy": 0.25, "valence": 0.55, "mood": "calm", "acousticness": 0.80}),
    (re.compile(r"\b(sad|dard|judai|alvida|tanha|tanhai|bewafa|rulaaye|aansu|dil[\s-]?toot|broken)\b", re.I),
     {"energy": 0.30, "valence": 0.22, "mood": "melancholic", "acousticness": 0.55}),
    (re.compile(r"\b(party|nachle|dance|dj|remix|club|bass|beat|thumka|garba|dandiya)\b", re.I),
     {"energy": 0.88, "valence": 0.82, "mood": "celebratory", "acousticness": 0.15}),
    (re.compile(r"\b(ishq|pyaar|mohabbat|prem|love|romantic|dil|sanam|jaaneman|mehboob)\b", re.I),
     {"energy": 0.50, "valence": 0.65, "mood": "focused", "acousticness": 0.45}),
    (re.compile(r"\b(rock|anthem|power|josh|ziddi|fighter|champion|unstoppable)\b", re.I),
     {"energy": 0.82, "valence": 0.70, "mood": "energized", "acousticness": 0.20}),
    (re.compile(r"\b(raag|raga|thumri|khayal|ghazal|tarana|dhrupad)\b", re.I),
     {"energy": 0.35, "valence": 0.50, "mood": "focused", "acousticness": 0.85}),
]

# Language → default genre/region mapping.
_LANGUAGE_DEFAULTS: dict[str, dict[str, str]] = {
    "hindi":    {"genre": "bollywood", "region": "India"},
    "marathi":  {"genre": "marathi",   "region": "Maharashtra"},
    "punjabi":  {"genre": "punjabi",   "region": "India"},
    "tamil":    {"genre": "kollywood", "region": "India"},
    "telugu":   {"genre": "tollywood", "region": "India"},
    "bengali":  {"genre": "bengali",   "region": "India"},
    "kannada":  {"genre": "sandalwood", "region": "India"},
    "malayalam": {"genre": "mollywood", "region": "India"},
    "english":  {"genre": "pop",       "region": "US"},
    "gujarati": {"genre": "gujarati",  "region": "India"},
    "bhojpuri": {"genre": "bhojpuri",  "region": "India"},
    "rajasthani": {"genre": "folk",    "region": "India"},
    "urdu":     {"genre": "ghazal",    "region": "India"},
}

_BASELINE = {
    "energy": 0.55,
    "valence": 0.55,
    "mood": "focused",
    "acousticness": 0.40,
    "instrumentalness": 0.02,
    "loudness": -8.0,
}


def estimate_audio_features(
    *,
    title: str | None = None,
    language: str | None = None,
    duration_ms: int | None = None,
    artist_name: str | None = None,
) -> dict:
    """Return estimated audio features + genre/region for a track.

    This is the HEURISTIC fallback — used only when real audio analysis
    is not possible (e.g. during import when we don't want to block on
    downloads). The management command `analyze_tracks` should be run
    afterwards to replace these with real measurements.

    Returns a dict with keys:
        energy, valence, acousticness, instrumentalness, loudness,
        primaryMood, genre, region, tempoBpm
    """
    features = dict(_BASELINE)

    clean_title = (title or "").strip()
    for pattern, overrides in _TITLE_SIGNALS:
        if pattern.search(clean_title):
            features.update(overrides)
            break

    lang = (language or "").strip().lower()
    lang_defaults = _LANGUAGE_DEFAULTS.get(lang, {})
    features["genre"] = lang_defaults.get("genre")
    features["region"] = lang_defaults.get("region")

    if duration_ms:
        minutes = duration_ms / 60_000
        if minutes < 2.0:
            features["energy"] = min(features["energy"] + 0.10, 1.0)
            features["valence"] = min(features["valence"] + 0.05, 1.0)
        elif minutes > 7.0:
            features["energy"] = max(features["energy"] - 0.10, 0.0)
            features["acousticness"] = min(features["acousticness"] + 0.15, 1.0)

    energy = features["energy"]
    tempo = int(80 + energy * 80)
    features["tempoBpm"] = max(40, min(220, tempo))

    if re.search(r"\b(instrumental|karaoke|bgm|score|theme)\b", clean_title, re.I):
        features["instrumentalness"] = 0.80
        features["energy"] = max(features["energy"] - 0.05, 0.0)

    features["primaryMood"] = derive_primary_mood({
        "energy": features["energy"],
        "valence": features["valence"],
    })

    features["loudness"] = round(-14.0 + features["energy"] * 10.0, 1)

    return features


def enrich_track_fields(track, *, save: bool = True, use_audio: bool = False) -> bool:
    """Fill in missing recommendation fields on a Track instance.

    Returns True if the track was updated, False if it was already complete.
    Only writes fields that are currently NULL — never overwrites existing
    data (e.g. if a track was later synced from Spotify, keep those values).

    If use_audio=True, attempts real audio analysis first. Falls back to
    heuristics if audio download/analysis fails.
    """
    needs_update = False
    update_fields = []

    has_features = all([
        track.energy is not None,
        track.valence is not None,
        track.primaryMood,
        track.genre,
    ])
    if has_features:
        return False

    # Try real audio analysis first if requested
    if use_audio:
        try:
            from concerts.audio_analyzer import analyze_track
            result = analyze_track(track, force=False)
            if result:
                # Audio analysis already saved the fields; check genre/region
                _fill_genre_region(track, update_fields)
                if update_fields and save:
                    track.save(update_fields=update_fields)
                return True
        except Exception as exc:
            logger.warning(
                "Audio analysis failed for track %s, falling back to heuristics: %s",
                track.id, exc,
            )

    # Heuristic fallback
    artist_name = getattr(track.artistId, "name", "") if track.artistId_id else ""
    estimated = estimate_audio_features(
        title=track.title,
        language=track.language,
        duration_ms=track.durationMs,
        artist_name=artist_name,
    )

    field_map = {
        "energy":           estimated.get("energy"),
        "valence":          estimated.get("valence"),
        "acousticness":     estimated.get("acousticness"),
        "instrumentalness": estimated.get("instrumentalness"),
        "loudness":         estimated.get("loudness"),
        "primaryMood":      estimated.get("primaryMood"),
        "genre":            estimated.get("genre"),
        "region":           estimated.get("region"),
        "tempoBpm":         estimated.get("tempoBpm"),
    }

    for field, value in field_map.items():
        if value is not None and getattr(track, field) is None:
            setattr(track, field, value)
            update_fields.append(field)
            needs_update = True

    if not track.primaryMood and estimated.get("primaryMood"):
        track.primaryMood = estimated["primaryMood"]
        if "primaryMood" not in update_fields:
            update_fields.append("primaryMood")
        needs_update = True

    if not track.genre and estimated.get("genre"):
        track.genre = estimated["genre"]
        if "genre" not in update_fields:
            update_fields.append("genre")
        needs_update = True

    if not track.region and estimated.get("region"):
        track.region = estimated["region"]
        if "region" not in update_fields:
            update_fields.append("region")
        needs_update = True

    if needs_update and save:
        track.save(update_fields=update_fields)

    return needs_update


def _fill_genre_region(track, update_fields: list) -> None:
    """Fill genre/region from language if still missing after audio analysis."""
    lang = (track.language or "").strip().lower()
    lang_defaults = _LANGUAGE_DEFAULTS.get(lang, {})

    if not track.genre and lang_defaults.get("genre"):
        track.genre = lang_defaults["genre"]
        update_fields.append("genre")

    if not track.region and lang_defaults.get("region"):
        track.region = lang_defaults["region"]
        update_fields.append("region")
