from __future__ import annotations

import os
import re
from urllib.parse import urlparse

class SpotifyConfigurationError(RuntimeError):
    """Raised when Spotify credentials are missing."""


class SpotifyImportError(RuntimeError):
    """Raised when Spotify requests fail."""


def get_access_token() -> str:
    client = _build_client()
    token_info = client.auth_manager.get_access_token(as_dict=True)
    return token_info["access_token"]


def search_tracks(query: str, limit: int = 20, market: str | None = None) -> list[dict]:
    client = _build_client()
    market_code = market or os.getenv("SPOTIFY_MARKET", "IN")

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

    return [
        _normalise_track_payload(item, feature_map.get(item.get("id")))
        for item in track_items
    ]


def get_track(track_url_or_id: str, market: str | None = None) -> dict:
    client = _build_client()
    track_id = extract_spotify_track_id(track_url_or_id)
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

    return _normalise_track_payload(item, audio_features)


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
        "audio_features": audio_features or {},
    }
