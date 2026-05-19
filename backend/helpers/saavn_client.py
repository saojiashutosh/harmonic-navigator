"""JioSaavn search client — find an artist's songs (key-free, India-strong).

JioSaavn exposes no official API; this targets the same internal endpoint the
site itself uses (jiosaavn.com/api.php) — the one music/views.py already uses
to resolve stream URLs and the import_saavn_songs command uses to seed tracks.

Concert Mode uses this to top up a thin local catalog with more of the
headline artist's songs before building the warm-up playlist.
"""
from __future__ import annotations

import html

import requests
from django.core.cache import cache

SAAVN_SEARCH_URL = "https://www.jiosaavn.com/api.php"

# JioSaavn results are stable; cache a few hours to avoid re-hitting the site.
_CACHE_TTL = 60 * 60 * 6

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.jiosaavn.com/",
}


class SaavnRequestError(RuntimeError):
    """Raised when a JioSaavn search request fails."""


def search_songs(query: str, *, limit: int = 30) -> list[dict]:
    """Return normalized JioSaavn songs for a query.

    Each dict: saavn_id, title, artist, language, year, duration_ms,
    is_explicit, image_url.
    """
    query = (query or "").strip()
    if not query:
        return []

    cache_key = f"saavn:search:{query.lower()}:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        response = requests.get(
            SAAVN_SEARCH_URL,
            params={
                "__call": "search.getResults",
                "q": query,
                "p": 1,
                "n": limit,
                "q_format": "1",
                "_format": "json",
                "_marker": "0",
            },
            headers=_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SaavnRequestError(f"JioSaavn search failed: {exc}") from exc

    results = (response.json() or {}).get("results") or []
    songs = [song for song in (_normalise_song(r) for r in results) if song]
    cache.set(cache_key, songs, _CACHE_TTL)
    return songs


def _normalise_song(song: dict) -> dict | None:
    title = html.unescape(
        (song.get("song") or song.get("title") or "").strip()
    )
    if not title:
        return None

    artist = html.unescape(
        (
            song.get("primary_artists")
            or song.get("singers")
            or song.get("music")
            or ""
        ).strip()
    )

    year_raw = song.get("year") or song.get("release_date") or ""
    try:
        year = int(str(year_raw)[:4])
    except (ValueError, TypeError):
        year = None
    if year and not (1900 <= year <= 2100):
        year = None

    raw_duration = song.get("duration") or ""
    try:
        if ":" in str(raw_duration):
            minutes, seconds = str(raw_duration).split(":")[:2]
            duration_ms = (int(minutes) * 60 + int(seconds)) * 1000
        else:
            duration_ms = int(float(raw_duration)) * 1000
    except (ValueError, TypeError):
        duration_ms = None

    return {
        "saavn_id": str(song.get("id") or ""),
        "title": title,
        "artist": artist,
        "language": (song.get("language") or "").lower().strip() or None,
        "year": year,
        "duration_ms": duration_ms,
        "is_explicit": str(song.get("explicit_content") or "0") == "1",
        "image_url": song.get("image"),
    }
