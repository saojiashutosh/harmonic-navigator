import base64
import re
import urllib.parse

import requests
from cryptography.hazmat.backends import default_backend
try:
    from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
except ImportError:
    from cryptography.hazmat.primitives.ciphers.algorithms import TripleDES
from cryptography.hazmat.primitives.ciphers import Cipher, modes
from rest_framework import status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from harmonic_navigator.views import HarmonicBaseViewSet
from moods.models import MoodSession

from . import filters, models, serializers
from .constants import EXPAND_COUNT, GUEST_PLAYLIST_SIZE, REGISTERED_PLAYLIST_SIZE
from .services import build_playlist_for_session, expand_playlist


class PlaylistViewSet(HarmonicBaseViewSet):
    queryset = models.Playlist.objects.all()
    serializer_class = serializers.PlaylistSerializer
    filterset_class = filters.PlaylistFilter
    permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'createdAt',
        'updatedAt',
        'confidence',
        'trackCount',
    )

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        serializer = serializers.GeneratePlaylistSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            session = MoodSession.objects.get(
                id=serializer.validated_data["moodSessionId"],
            )
        except MoodSession.DoesNotExist:
            return Response({"detail": "Mood session not found."}, status=status.HTTP_404_NOT_FOUND)

        # Playlist size is determined by auth status, not the frontend request.
        if request.user.is_anonymous:
            limit = GUEST_PLAYLIST_SIZE
        else:
            limit = REGISTERED_PLAYLIST_SIZE

        try:
            playlist = build_playlist_for_session(session, limit=limit)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            self.get_serializer(playlist).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="expand",
        permission_classes=[IsAuthenticated],
    )
    def expand(self, request, pk=None):
        """Add EXPAND_COUNT more tracks to an existing playlist.

        Requires authentication. Works for both guest-created and
        user-owned playlists so users can expand a playlist they
        generated before logging in.
        """
        playlist = self.get_object()

        try:
            playlist = expand_playlist(playlist, extra=EXPAND_COUNT)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.get_serializer(playlist).data, status=status.HTTP_200_OK)


class PlaylistTrackViewSet(HarmonicBaseViewSet):
    queryset = models.PlaylistTrack.objects.all()
    serializer_class = serializers.PlaylistTrackSerializer
    filterset_class = filters.PlaylistTrackFilter
    permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'createdAt',
        'updatedAt',
        'position',
    )

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("playlistId", "trackId", "trackId__artistId")
        )


class SavedPlaylistViewSet(HarmonicBaseViewSet):
    queryset = models.SavedPlaylist.objects.all()
    serializer_class = serializers.SavedPlaylistSerializer
    filterset_class = filters.SavedPlaylistFilter
    permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'updatedAt',
    )




_SAAVN_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.jiosaavn.com/',
}

_DES_KEY = b'38346591'


def _decrypt_saavn_url(encrypted_url: str) -> str:
    enc_bytes = base64.b64decode(encrypted_url)
    cipher = Cipher(TripleDES(_DES_KEY * 3), modes.ECB(), backend=default_backend())
    dec = cipher.decryptor()
    result = dec.update(enc_bytes) + dec.finalize()
    # Strip PKCS5 padding (each pad byte == number of pad bytes, max 8 for DES)
    pad_len = result[-1] if 1 <= result[-1] <= 8 else 0
    return result[:len(result) - pad_len].decode('utf-8').strip()


@api_view(['GET'])
@permission_classes([AllowAny])
def saavn_search(request):
    """Return a full-quality JioSaavn audio URL for a track.

    Pass track_id to enable DB caching — cached URLs are returned instantly
    without hitting JioSaavn. On first fetch the URL is saved to Track.streamUrl.
    """
    from tracks.models import Track as TrackModel

    query = request.query_params.get('q', '').strip()
    track_id = request.query_params.get('track_id', '').strip()

    # Return cached URL if available
    if track_id:
        try:
            track = TrackModel.objects.get(id=track_id)
            if track.streamUrl:
                return Response({"audioUrl": track.streamUrl, "cached": True})
            # Build query from DB data if caller didn't provide one
            if not query:
                artist = track.artistId.name if track.artistId else ''
                query = f"{track.title} {artist}".strip()
        except TrackModel.DoesNotExist:
            track = None
    else:
        track = None

    if not query:
        return Response({"error": "Query parameter 'q' is required."}, status=status.HTTP_400_BAD_REQUEST)

    def _fetch_songs(q, n=8):
        """Return top-n JioSaavn results for query q."""
        r = requests.get(
            'https://www.jiosaavn.com/api.php',
            params={'__call': 'search.getResults', 'q': q, 'p': 1,
                    'q_format': '1', '_format': 'json', '_marker': '0', 'n': n},
            headers=_SAAVN_HEADERS, timeout=10,
        )
        r.raise_for_status()
        return r.json().get('results') or []

    def _words(text):
        return set(re.sub(r'[^\w\s]', '', (text or '').lower()).split())

    def _score_result(result, target_title_words, target_artist_words):
        song_title = result.get('song') or result.get('title') or ''
        song_artist = result.get('primary_artists') or result.get('singers') or ''
        title_words = _words(song_title)
        artist_words = _words(song_artist)
        if not title_words or not target_title_words:
            return 0.0
        title_overlap = len(target_title_words & title_words) / max(len(target_title_words), len(title_words))
        artist_bonus = 0.25 if (target_artist_words and target_artist_words & artist_words) else 0.0
        return title_overlap + artist_bonus

    def _best_match(candidates, target_title_words, target_artist_words):
        if not candidates:
            return None
        scored = [(c, _score_result(c, target_title_words, target_artist_words)) for c in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    # Determine what to match against — prefer DB title/artist over raw query
    if track:
        _target_title = track.title or query
        _target_artist = track.artistId.name if track.artistId else ''
    else:
        _target_title = query
        _target_artist = ''

    _title_words = _words(_target_title)
    _artist_words = _words(_target_artist)

    try:
        # Search title-only first (avoids artist name polluting results),
        # then also search title+artist; combine and pick the best title match.
        candidates = _fetch_songs(_target_title)
        if _target_artist:
            combined_q = f"{_target_title} {_target_artist}"
            if combined_q != query:
                candidates += _fetch_songs(combined_q)
        elif query != _target_title:
            candidates += _fetch_songs(query)

        # Deduplicate by song id
        seen, unique = set(), []
        for c in candidates:
            sid = c.get('id') or c.get('song_id') or ''
            if sid not in seen:
                seen.add(sid)
                unique.append(c)

        song = _best_match(unique, _title_words, _artist_words)

        # Fallback: if no candidates at all, try dropping artist from original query
        if not song and ' ' in query:
            short = query.rsplit(' ', 1)[0]
            song = _best_match(_fetch_songs(short), _title_words, _artist_words)

        if not song:
            return Response({"error": "No results found."}, status=status.HTTP_404_NOT_FOUND)

        encrypted_url = song.get('encrypted_media_url')
        if not encrypted_url:
            return Response({"error": "No encrypted URL in result."}, status=status.HTTP_404_NOT_FOUND)

        # Decrypt DES-ECB URL and upgrade to 320kbps if available
        audio_url = _decrypt_saavn_url(encrypted_url)
        if song.get('320kbps') == 'true':
            audio_url = audio_url.replace('_96.mp4', '_320.mp4') \
                                 .replace('_160.mp4', '_320.mp4')

        # Persist to DB so next call is instant
        if track:
            TrackModel.objects.filter(id=track.id).update(streamUrl=audio_url)

        return Response({"audioUrl": audio_url, "cached": False})

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def youtube_search(request):
    """Search YouTube for a song and return the best-matching video ID.

    Strategy:
    1. Build a precise query: the frontend sends "Title Artist official audio".
       We pass it unchanged — no extra "song" or "lyrics" suffix that can confuse
       non-English / instrumental tracks.
    2. Scrape YouTube search results and extract videoIds.
    3. Filter out IDs that appear *only* inside playlist/channel/mix context
       markers (those are not standalone watch-page links).
    4. Return the first clean candidate.  If none found without filter, retry
       without the video-type sp param as a last resort.
    """
    query = request.query_params.get('q', '').strip()
    if not query:
        return Response(
            {"error": "Query parameter 'q' is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Use the query exactly as sent by the frontend (already includes
    # "official audio").  We only add "audio" if the word isn't already there.
    if 'audio' not in query.lower() and 'lyrics' not in query.lower():
        search_query = f'{query} audio'
    else:
        search_query = query

    encoded_q = urllib.parse.quote(search_query)

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0.0.0 Safari/537.36'
        ),
        'Accept-Language': 'en-US,en;q=0.9',
    }

    # EgIQAQ== is the base64-encoded YouTube "video only" search filter.
    # Single-percent-encoded in the URL string (NOT double-encoded).
    VIDEO_FILTER = 'EgIQAQ%3D%3D'

    playlist_ctx_re = re.compile(
        r'"(?:playlistId|channelId|radioId|mixId|list)":\s*"[^"]*"'
    )
    video_id_re = re.compile(r'"videoId":"([a-zA-Z0-9_-]{11})"')

    def _extract_best_id(html):
        """Return the first standalone video ID from scraped YouTube HTML."""
        # Mark IDs that only appear adjacent to playlist/channel context keys.
        playlist_adjacent = set()
        for m in video_id_re.finditer(html):
            vid = m.group(1)
            window = html[max(0, m.start() - 80): m.end() + 80]
            if playlist_ctx_re.search(window):
                playlist_adjacent.add(vid)

        seen = set()
        clean = []
        fallback = []
        for m in video_id_re.finditer(html):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            if vid.startswith('-'):   # malformed / YouTube-internal id
                continue
            if vid in playlist_adjacent:
                fallback.append(vid)
            else:
                clean.append(vid)

        candidates = clean or fallback
        return candidates[0] if candidates else None

    try:
        # Attempt 1: with YouTube "video only" filter
        res = requests.get(
            f'https://www.youtube.com/results?search_query={encoded_q}&sp={VIDEO_FILTER}',
            headers=headers,
            timeout=10,
        )
        video_id = _extract_best_id(res.text)

        # Attempt 2: without filter (broader fallback)
        if not video_id:
            res2 = requests.get(
                f'https://www.youtube.com/results?search_query={encoded_q}',
                headers=headers,
                timeout=10,
            )
            video_id = _extract_best_id(res2.text)

        if video_id:
            return Response({"videoId": video_id})

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {"error": "No video found."},
        status=status.HTTP_404_NOT_FOUND,
    )
