"""Heuristic audio-feature estimation for tracks without Spotify features.

Concert-sourced tracks arrive from JioSaavn with only basic metadata (title,
language, year, duration).  The survey-based recommendation engine scores
every track on energy, valence, primaryMood, genre, region, acousticness,
instrumentalness and loudness — so concert tracks are invisible to it.

This module estimates those fields from whatever JioSaavn *does* provide
(language, duration, title keywords, artist name) plus curated keyword
heuristics.  The estimates are deliberately coarse — just good enough to
place a song in the right mood-bucket so the playlist builder can rank it.

When the Spotify audio-features API becomes available again, these heuristic
values should be replaced by real measurements.
"""
from __future__ import annotations

import re

from tracks.services import derive_primary_mood


# ── Title-keyword → mood/energy/valence heuristics ──────────────────────
# Scanned case-insensitively against the track title.  First match wins,
# so order matters: more specific patterns come first.
_TITLE_SIGNALS: list[tuple[re.Pattern, dict]] = [
    # Calm / ambient
    (re.compile(r"\b(lori|lullaby|cradle|lofi|lo[\s-]?fi|slowed|reverb)\b", re.I),
     {"energy": 0.20, "valence": 0.40, "mood": "calm", "acousticness": 0.75}),

    # Devotional / spiritual — calm mood
    (re.compile(r"\b(bhajan|aarti|kirtan|mantra|chalisa|stotra|shlok|abhang|vandana|bhakti|qawwali)\b", re.I),
     {"energy": 0.25, "valence": 0.55, "mood": "calm", "acousticness": 0.80}),

    # Sad / melancholic signals
    (re.compile(r"\b(sad|dard|judai|alvida|tanha|tanhai|bewafa|rulaaye|aansu|dil[\s-]?toot|broken)\b", re.I),
     {"energy": 0.30, "valence": 0.22, "mood": "melancholic", "acousticness": 0.55}),

    # Party / celebratory
    (re.compile(r"\b(party|nachle|dance|dj|remix|club|bass|beat|thumka|garba|dandiya)\b", re.I),
     {"energy": 0.88, "valence": 0.82, "mood": "celebratory", "acousticness": 0.15}),

    # Romantic — moderate energy, high valence
    (re.compile(r"\b(ishq|pyaar|mohabbat|prem|love|romantic|dil|sanam|jaaneman|mehboob)\b", re.I),
     {"energy": 0.50, "valence": 0.65, "mood": "focused", "acousticness": 0.45}),

    # Energetic / motivational
    (re.compile(r"\b(rock|anthem|power|josh|ziddi|fighter|champion|unstoppable)\b", re.I),
     {"energy": 0.82, "valence": 0.70, "mood": "energized", "acousticness": 0.20}),

    # Classical / raga forms
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

# Baseline audio features when no title-keyword signal matches.
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

    Returns a dict with keys:
        energy, valence, acousticness, instrumentalness, loudness,
        primaryMood, genre, region, tempoBpm
    """
    features = dict(_BASELINE)

    # ── Title keyword scan ──────────────────────────────────────────
    clean_title = (title or "").strip()
    for pattern, overrides in _TITLE_SIGNALS:
        if pattern.search(clean_title):
            features.update(overrides)
            break

    # ── Language-derived genre/region ────────────────────────────────
    lang = (language or "").strip().lower()
    lang_defaults = _LANGUAGE_DEFAULTS.get(lang, {})
    features["genre"] = lang_defaults.get("genre")
    features["region"] = lang_defaults.get("region")

    # ── Duration-based adjustments ──────────────────────────────────
    # Very short tracks (< 2 min) tend to be upbeat intros/jingles;
    # very long tracks (> 7 min) tend to be slower/classical.
    if duration_ms:
        minutes = duration_ms / 60_000
        if minutes < 2.0:
            features["energy"] = min(features["energy"] + 0.10, 1.0)
            features["valence"] = min(features["valence"] + 0.05, 1.0)
        elif minutes > 7.0:
            features["energy"] = max(features["energy"] - 0.10, 0.0)
            features["acousticness"] = min(features["acousticness"] + 0.15, 1.0)

    # ── Estimate tempo from energy (rough heuristic) ────────────────
    energy = features["energy"]
    tempo = int(80 + energy * 80)  # range ~80-160 BPM
    features["tempoBpm"] = max(40, min(220, tempo))

    # ── Instrumentalness for instrumental-looking titles ────────────
    if re.search(r"\b(instrumental|karaoke|bgm|score|theme)\b", clean_title, re.I):
        features["instrumentalness"] = 0.80
        features["energy"] = max(features["energy"] - 0.05, 0.0)

    # ── Derive primaryMood using the standard engine function ───────
    features["primaryMood"] = derive_primary_mood({
        "energy": features["energy"],
        "valence": features["valence"],
    })

    # Loudness estimate from energy (louder tracks = higher energy)
    features["loudness"] = round(-14.0 + features["energy"] * 10.0, 1)

    return features


def enrich_track_fields(track, *, save: bool = True) -> bool:
    """Fill in missing recommendation fields on a Track instance.

    Returns True if the track was updated, False if it was already complete.
    Only writes fields that are currently NULL — never overwrites existing
    data (e.g. if a track was later synced from Spotify, keep those values).
    """
    needs_update = False
    update_fields = []

    # Check if the track already has the key recommendation fields
    has_features = all([
        track.energy is not None,
        track.valence is not None,
        track.primaryMood,
        track.genre,
    ])
    if has_features:
        return False

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

    # Also set primaryMood if it was blank string
    if not track.primaryMood and estimated.get("primaryMood"):
        track.primaryMood = estimated["primaryMood"]
        if "primaryMood" not in update_fields:
            update_fields.append("primaryMood")
        needs_update = True

    # Also set genre if it was blank string
    if not track.genre and estimated.get("genre"):
        track.genre = estimated["genre"]
        if "genre" not in update_fields:
            update_fields.append("genre")
        needs_update = True

    # Also set region if it was blank string
    if not track.region and estimated.get("region"):
        track.region = estimated["region"]
        if "region" not in update_fields:
            update_fields.append("region")
        needs_update = True

    if needs_update and save:
        track.save(update_fields=update_fields)

    return needs_update
