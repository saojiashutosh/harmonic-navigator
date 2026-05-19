"""setlist.fm API client — recent setlists for an artist.

Free API key: request one at https://www.setlist.fm/settings/api.
Set SETLISTFM_API_KEY in the environment to enable setlist-weighted playlists.
"""
from __future__ import annotations

import os
from collections import Counter

import requests
from django.core.cache import cache

SETLISTFM_SEARCH_URL = "https://api.setlist.fm/rest/1.0/search/setlists"

# Setlists rarely change; cache aggressively to stay within the free-tier limit.
_CACHE_TTL = 60 * 60 * 12

# How many of the artist's most recent shows to aggregate into the weighting.
_MAX_SETLISTS = 10


class SetlistFmConfigurationError(RuntimeError):
    """Raised when the setlist.fm API key is missing."""


class SetlistFmRequestError(RuntimeError):
    """Raised when a setlist.fm request fails."""


def _api_key() -> str:
    key = (os.getenv("SETLISTFM_API_KEY") or "").strip()
    if not key:
        raise SetlistFmConfigurationError(
            "setlist.fm API key is missing. Set SETLISTFM_API_KEY to enable "
            "setlist-weighted playlists."
        )
    return key


def recent_setlists(artist_name: str, *, song_limit: int = 40) -> list[dict]:
    """Return [{song, count}] aggregated across an artist's recent setlists.

    `count` is how many of the recent shows featured the song — the weighting
    signal a concert-prep playlist leans on. Returns an empty list when the
    artist has no setlists on file.
    """
    artist_name = (artist_name or "").strip()
    if not artist_name:
        return []

    cache_key = f"setlistfm:recent:{artist_name.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    headers = {
        "x-api-key": _api_key(),
        "Accept": "application/json",
        "User-Agent": "HarmonicNavigator/1.0",
    }

    try:
        response = requests.get(
            SETLISTFM_SEARCH_URL,
            params={"artistName": artist_name, "p": 1},
            headers=headers,
            timeout=12,
        )
        if response.status_code == 404:
            # No setlists for this artist — a normal, cacheable outcome.
            cache.set(cache_key, [], _CACHE_TTL)
            return []
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SetlistFmRequestError(f"setlist.fm request failed: {exc}") from exc

    setlists = (response.json() or {}).get("setlist") or []

    counter: Counter = Counter()
    for setlist in setlists[:_MAX_SETLISTS]:
        for song in _songs_in_setlist(setlist):
            counter[song] += 1

    aggregated = [
        {"song": song, "count": count}
        for song, count in counter.most_common(song_limit)
    ]
    cache.set(cache_key, aggregated, _CACHE_TTL)
    return aggregated


def _songs_in_setlist(setlist: dict) -> list[str]:
    songs: list[str] = []
    for set_block in (setlist.get("sets") or {}).get("set") or []:
        for song in set_block.get("song") or []:
            name = (song.get("name") or "").strip()
            if name:
                songs.append(name)
    return songs
