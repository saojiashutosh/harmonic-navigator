from __future__ import annotations

import hashlib
import json

# ── TTL constants (seconds) ──────────────────────────────────────────────────
CANDIDATE_POOL_TTL = 3_600      # 1 hour  — refresh when tracks are imported
AI_MOOD_TTL = 86_400            # 24 hours — Groq output is deterministic
SPOTIFY_TRACK_TTL = 86_400      # 24 hours — track metadata is stable
SPOTIFY_SEARCH_TTL = 3_600      # 1 hour  — new tracks may surface on Spotify
QUESTIONS_TTL = 3_600           # 1 hour  — questionnaire rarely changes


# ── Key builders ─────────────────────────────────────────────────────────────

def pool_cache_key(
    mood_label: str,
    secondary_mood: str | None,
    social_setting: str | None,
    music_language: str | None,
    preferred_artist: str | None,
    era_preference: str | None,
) -> str:
    params = {
        "mood": mood_label,
        "secondary": secondary_mood,
        "social": social_setting,
        "lang": music_language,
        "artist": preferred_artist,
        "era": era_preference,
    }
    return f"harmonic:pool:{_sha(params)}"


def ai_mood_cache_key(answers: list[dict]) -> str:
    # Sort list by question_key so ordering doesn't break cache hits.
    stable = sorted(answers, key=lambda a: a.get("question_key", ""))
    return f"harmonic:ai_mood:{_sha(stable)}"


def spotify_track_cache_key(track_id: str) -> str:
    return f"harmonic:spotify:track:{track_id}"


def spotify_search_cache_key(query: str, limit: int, market: str | None) -> str:
    return f"harmonic:spotify:search:{_sha({'q': query, 'limit': limit, 'market': market})}"


QUESTIONS_CACHE_KEY = "harmonic:questions:active"

POOL_CACHE_PATTERN = "harmonic:pool:*"


def _sha(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:20]
