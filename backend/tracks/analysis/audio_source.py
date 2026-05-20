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


def _words(text) -> set:
    """Lower-cased word set with punctuation stripped."""
    return set(re.sub(r"[^\w\s]", " ", str(text or "").lower()).split())


def _contained(query_words: set, target_words: set) -> float:
    """Fraction of ``query_words`` present in ``target_words`` (0-1)."""
    if not query_words:
        return 0.0
    return len(query_words & target_words) / len(query_words)


def _result_artist_text(result: dict) -> str:
    """Best-effort artist string from a JioSaavn search result."""
    parts = [result.get("subtitle"), result.get("primary_artists"),
             result.get("singers")]
    more_info = result.get("more_info") or {}
    parts += [more_info.get("singers"), more_info.get("primary_artists")]
    return " ".join(str(p) for p in parts if p)


def _match_score(result: dict, title: str, artist_name: str) -> float:
    """Confidence (0-1) that a JioSaavn result is the song we asked for.

    Combines how much of the requested title and artist appear in the
    result — so covers, remixes by other artists and wrong songs score low.
    """
    res_title = result.get("song") or result.get("title") or ""
    title_score = _contained(_words(title), _words(res_title))

    artist_words = _words(artist_name)
    if not artist_words:
        return title_score
    artist_score = _contained(artist_words, _words(_result_artist_text(result)))
    return 0.6 * title_score + 0.4 * artist_score


def resolve_stream_url(
    title: str, artist_name: str = "", *, min_match: float = 0.0
) -> str:
    """Search JioSaavn for a song and return its decrypted stream URL.

    ``min_match`` (0-1) rejects low-confidence matches: if the best result
    scores below it, ``AudioAnalysisError`` is raised instead of returning
    a likely-wrong recording. Default 0.0 keeps the lenient behaviour.
    """
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

    # Pick the result that best matches both title and artist.
    best, best_score = results[0], -1.0
    for result in results:
        score = _match_score(result, title, artist_name)
        if score > best_score:
            best, best_score = result, score

    if best_score < min_match:
        raise AudioAnalysisError(
            f"Low JioSaavn match confidence ({best_score:.2f}) for: {query}"
        )

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


def fetch_track_audio(
    title: str, artist_name: str = "", stream_url: str = "", *, min_match: float = 0.0
) -> tuple[bytes, str]:
    """Fetch a track's audio. Returns ``(audio_bytes, resolved_url)``.

    Uses ``stream_url`` directly when supplied, otherwise searches JioSaavn.
    ``min_match`` is forwarded to :func:`resolve_stream_url` to reject
    low-confidence matches.
    """
    audio_url = stream_url or resolve_stream_url(
        title, artist_name, min_match=min_match
    )
    audio_bytes = download_audio(audio_url)
    if len(audio_bytes) < 10_000:
        raise AudioAnalysisError(
            f"Audio too small ({len(audio_bytes)} bytes) for: {title}"
        )
    return audio_bytes, audio_url
