"""Audio acquisition — turn a Track into raw audio bytes to analyze.

The engine computes every feature itself; this module only *fetches the
sound*. JioSaavn is used purely as the catalogue / streaming source (the
same source the rest of the app already plays from) — it never supplies
any analysed feature. Decryption and search mirror ``playlists/views.py``.
"""
from __future__ import annotations

import base64
import logging
import re

import requests

logger = logging.getLogger(__name__)

# JioSaavn web API headers (identical to the rest of the project).
_SAAVN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.jiosaavn.com/",
}

# DES key JioSaavn uses to encrypt its media URLs.
_DES_KEY = b"38346591"

# Largest audio payload we will pull (a 320kbps 5-min track is ~12 MB).
_MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024


class AudioAnalysisError(RuntimeError):
    """Raised when audio cannot be fetched or analysed."""


def decrypt_saavn_url(encrypted_url: str) -> str:
    """Decrypt JioSaavn's DES-ECB encrypted media URL into a playable URL."""
    try:
        from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
    except ImportError:  # older cryptography releases
        from cryptography.hazmat.primitives.ciphers.algorithms import TripleDES
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers import Cipher, modes

    enc_bytes = base64.b64decode(encrypted_url)
    cipher = Cipher(TripleDES(_DES_KEY * 3), modes.ECB(), backend=default_backend())
    decryptor = cipher.decryptor()
    result = decryptor.update(enc_bytes) + decryptor.finalize()
    pad_len = result[-1] if 1 <= result[-1] <= 8 else 0
    return result[: len(result) - pad_len].decode("utf-8").strip()


def resolve_stream_url(title: str, artist_name: str = "") -> str:
    """Search JioSaavn for a song and return its decrypted stream URL."""
    query = f"{title} {artist_name}".strip()
    if not query:
        raise AudioAnalysisError("Cannot resolve stream URL: no title/artist")

    response = requests.get(
        "https://www.jiosaavn.com/api.php",
        params={
            "__call": "search.getResults",
            "q": query,
            "p": 1,
            "n": 5,
            "q_format": "1",
            "_format": "json",
            "_marker": "0",
        },
        headers=_SAAVN_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    results = (response.json() or {}).get("results") or []
    if not results:
        raise AudioAnalysisError(f"No JioSaavn results for: {query}")

    # Pick the result whose title overlaps ours the most.
    target_words = set(re.sub(r"[^\w\s]", "", title.lower()).split())
    best, best_score = results[0], 0.0
    for result in results:
        song_title = result.get("song") or result.get("title") or ""
        words = set(re.sub(r"[^\w\s]", "", song_title.lower()).split())
        if not words or not target_words:
            continue
        overlap = len(target_words & words) / max(len(target_words), len(words))
        if overlap > best_score:
            best, best_score = result, overlap

    encrypted_url = best.get("encrypted_media_url")
    if not encrypted_url:
        raise AudioAnalysisError("JioSaavn result has no encrypted media URL")

    audio_url = decrypt_saavn_url(encrypted_url)
    # Prefer the 320kbps master when JioSaavn flags it as available.
    if best.get("320kbps") == "true":
        audio_url = audio_url.replace("_96.mp4", "_320.mp4").replace(
            "_160.mp4", "_320.mp4"
        )
    return audio_url


def download_audio(url: str) -> bytes:
    """Download an audio URL and return its raw bytes (capped in size)."""
    response = requests.get(
        url,
        headers={"User-Agent": _SAAVN_HEADERS["User-Agent"]},
        timeout=30,
        stream=True,
    )
    response.raise_for_status()

    chunks, total = [], 0
    for chunk in response.iter_content(chunk_size=65536):
        chunks.append(chunk)
        total += len(chunk)
        if total > _MAX_DOWNLOAD_BYTES:
            break
    return b"".join(chunks)


def fetch_track_audio(title: str, artist_name: str = "", stream_url: str = "") -> tuple[bytes, str]:
    """Fetch a track's audio. Returns ``(audio_bytes, resolved_url)``.

    Uses ``stream_url`` directly when supplied, otherwise searches JioSaavn.
    """
    audio_url = stream_url or resolve_stream_url(title, artist_name)
    audio_bytes = download_audio(audio_url)
    if len(audio_bytes) < 10_000:
        raise AudioAnalysisError(
            f"Audio too small ({len(audio_bytes)} bytes) for: {title}"
        )
    return audio_bytes, audio_url
