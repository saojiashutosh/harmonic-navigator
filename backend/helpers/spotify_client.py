from __future__ import annotations

import os
import re
import json
import urllib.request
import urllib.parse
from urllib.parse import urlparse

from django.core.cache import cache

from helpers.cache_utils import (
    SPOTIFY_SEARCH_TTL,
    SPOTIFY_TRACK_TTL,
    spotify_search_cache_key,
    spotify_track_cache_key,
)

class SpotifyConfigurationError(RuntimeError):
    """Raised when Spotify credentials are missing."""


class SpotifyImportError(RuntimeError):
    """Raised when Spotify requests fail."""


def get_access_token() -> str:
    client = _build_client()
    token_info = client.auth_manager.get_access_token(as_dict=True)
    return token_info["access_token"]


def search_tracks(query: str, limit: int = 20, market: str | None = None) -> list[dict]:
    market_code = market or os.getenv("SPOTIFY_MARKET", "IN")
    key = spotify_search_cache_key(query, limit, market_code)
    cached = cache.get(key)
    if cached is not None:
        return cached

    client = _build_client()

    try:
        from spotipy.exceptions import SpotifyException

        response = client.search(
            q=query,
            type="track",
            limit=limit,
            market=market_code,
        )
        track_items = response.get("tracks", {}).get("items", [])
        spotify_ids = [item["id"] for item in track_items if item.get("id")]
    except SpotifyException as exc:
        raise SpotifyImportError(f"Spotify request failed: {exc}") from exc

    feature_rows = []
    # Disabled due to Spotify API restriction (403 errors)
    # if spotify_ids:
    #     try:
    #         from spotipy.exceptions import SpotifyException
    #         feature_rows = client.audio_features(spotify_ids) or []
    #     except SpotifyException:
    #         feature_rows = []

    feature_map = {
        feature["id"]: feature
        for feature in (feature_rows or [])
        if feature and feature.get("id")
    }

    results = [
        _normalise_track_payload(item, feature_map.get(item.get("id")))
        for item in track_items
    ]
    cache.set(key, results, SPOTIFY_SEARCH_TTL)
    return results


def get_track(track_url_or_id: str, market: str | None = None) -> dict:
    track_id = extract_spotify_track_id(track_url_or_id)
    key = spotify_track_cache_key(track_id)
    cached = cache.get(key)
    if cached is not None:
        return cached

    client = _build_client()
    market_code = market or os.getenv("SPOTIFY_MARKET", "IN")

    try:
        from spotipy.exceptions import SpotifyException

        item = client.track(track_id, market=market_code)
    except SpotifyException as exc:
        raise SpotifyImportError(f"Spotify track request failed: {exc}") from exc

    audio_features = {}
    # Disabled due to Spotify API restriction (403 errors)
    # try:
    #     from spotipy.exceptions import SpotifyException
    #     audio_features = client.audio_features([track_id])[0] or {}
    # except SpotifyException:
    #     audio_features = {}

    result = _normalise_track_payload(item, audio_features)
    cache.set(key, result, SPOTIFY_TRACK_TTL)
    return result


def get_playlist_tracks(playlist_url_or_id: str, market: str | None = None) -> list[dict]:
    playlist_id = extract_spotify_playlist_id(playlist_url_or_id)
    market_code = market or os.getenv("SPOTIFY_MARKET", "IN")

    # Try official API first; fall back to web-player token for playlists
    # that return 403 under client-credentials (editorial / other-user playlists).
    try:
        return _playlist_tracks_api(playlist_id, market_code)
    except SpotifyImportError:
        pass

    return _playlist_tracks_webplayer(playlist_id)


def _playlist_tracks_api(playlist_id: str, market_code: str) -> list[dict]:
    client = _build_client()
    try:
        from spotipy.exceptions import SpotifyException

        results = []
        offset = 0
        while True:
            response = client.playlist_items(
                playlist_id,
                market=market_code,
                limit=100,
                offset=offset,
                additional_types=["track"],
            )
            for item in response.get("items", []):
                track = item.get("track")
                if track and track.get("id") and track.get("type") == "track":
                    results.append(_normalise_track_payload(track, {}))
            if response.get("next") is None:
                break
            offset += 100
        return results
    except SpotifyException as exc:
        raise SpotifyImportError(f"Spotify playlist request failed: {exc}") from exc


def _get_webplayer_token() -> str:
    """Fetch the anonymous access token that Spotify's own web player uses.

    This token works for public playlists including editorial/Spotify-owned ones
    that the developer-credentials flow can't access (403).
    """
    url = "https://open.spotify.com/get_access_token?reason=transport&productType=web_player"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            token = data.get("accessToken")
            if not token:
                raise SpotifyImportError("Web player token endpoint returned no token.")
            return token
    except Exception as exc:
        raise SpotifyImportError(f"Could not obtain Spotify web-player token: {exc}") from exc


def _playlist_tracks_webplayer(playlist_id: str) -> list[dict]:
    """Fetch playlist tracks using Spotify's web-player anonymous token."""
    token = _get_webplayer_token()
    results = []
    url = (
        f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        f"?limit=100&offset=0&additional_types=track"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    while url:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                page = json.loads(resp.read())
        except Exception as exc:
            raise SpotifyImportError(f"Web-player playlist fetch failed: {exc}") from exc

        for item in page.get("items", []):
            track = item.get("track")
            if track and track.get("id") and track.get("type") == "track":
                results.append(_normalise_track_payload(track, {}))

        url = page.get("next")

    return results


def extract_spotify_playlist_id(playlist_url_or_id: str) -> str:
    value = playlist_url_or_id.strip()
    if not value:
        raise SpotifyImportError("Spotify playlist URL or ID is required.")

    parsed = urlparse(value)
    if parsed.netloc:
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] == "playlist":
            return parts[1].split("?")[0]

    if re.fullmatch(r"[A-Za-z0-9]{22}", value):
        return value

    raise SpotifyImportError("Invalid Spotify playlist URL or ID.")


def extract_spotify_track_id(track_url_or_id: str) -> str:
    value = track_url_or_id.strip()
    if not value:
        raise SpotifyImportError("Spotify track URL or ID is required.")

    parsed = urlparse(value)
    if parsed.netloc:
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] == "track":
            return parts[1]

    if re.fullmatch(r"[A-Za-z0-9]{22}", value):
        return value

    raise SpotifyImportError("Invalid Spotify track URL or ID.")


def _build_client() -> "Spotify":
    try:
        from spotipy import Spotify
        from spotipy.oauth2 import SpotifyClientCredentials
    except ModuleNotFoundError as exc:
        raise SpotifyConfigurationError(
            "spotipy is not installed in this environment. Install dependencies before using Spotify import."
        ) from exc

    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SpotifyConfigurationError(
            "Spotify credentials are missing. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET."
        )

    auth_manager = SpotifyClientCredentials(
        client_id=client_id,
        client_secret=client_secret,
    )
    return Spotify(auth_manager=auth_manager, requests_timeout=10, retries=3)


def _normalise_track_payload(item: dict, audio_features: dict | None) -> dict:
    artist = (item.get("artists") or [{}])[0]
    external_urls = item.get("external_urls") or {}
    album = item.get("album") or {}
    release_date = album.get("release_date") or item.get("release_date") or ""
    release_year = None
    if release_date:
        try:
            release_year = int(str(release_date)[:4])
        except (ValueError, TypeError):
            pass

    return {
        "spotify_id": item.get("id"),
        "title": item.get("name"),
        "artist": {
            "spotify_id": artist.get("id"),
            "name": artist.get("name"),
        },
        "preview_url": item.get("preview_url"),
        "external_url": external_urls.get("spotify"),
        "duration_ms": item.get("duration_ms"),
        "is_explicit": bool(item.get("explicit", False)),
        "release_year": release_year,
        "audio_features": audio_features or {},
    }
