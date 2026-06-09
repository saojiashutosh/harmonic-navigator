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
from django.db import transaction
from django.db.models import F, Max
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from harmonic_navigator.views import HarmonicBaseViewSet
from moods.models import MoodSession
from tracks.models import Track

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
        url_path="save-as",
        permission_classes=[IsAuthenticated],
    )
    def save_as(self, request, pk=None):
        """Save a generated playlist under a user-chosen name.

        Claims an unowned (guest) playlist for the current user, marks it
        saved, and creates a SavedPlaylist bookmark with the custom name.
        """
        playlist = self.get_object()
        serializer = serializers.SavePlaylistAsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["name"].strip()

        with transaction.atomic():
            update_fields = []
            if playlist.userId_id is None:
                playlist.userId = request.user
                update_fields.append("userId")
            if not playlist.isSaved:
                playlist.isSaved = True
                playlist.savedAt = timezone.now()
                update_fields += ["isSaved", "savedAt"]
            if update_fields:
                playlist.save(update_fields=update_fields)

            saved, created = models.SavedPlaylist.objects.update_or_create(
                userId=request.user,
                playlistId=playlist,
                defaults={"name": name},
            )

        return Response(
            serializers.SavedPlaylistSerializer(saved).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="add-track",
        permission_classes=[IsAuthenticated],
    )
    def add_track(self, request, pk=None):
        """Append a single track to a user-owned saved playlist."""
        playlist = self.get_object()

        if not models.SavedPlaylist.objects.filter(
            userId=request.user, playlistId=playlist
        ).exists():
            return Response(
                {"detail": "You can only add tracks to playlists you've saved."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = serializers.AddTrackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        track_id = serializer.validated_data["trackId"]

        try:
            track = Track.objects.get(id=track_id)
        except Track.DoesNotExist:
            return Response({"detail": "Track not found."}, status=status.HTTP_404_NOT_FOUND)

        if models.PlaylistTrack.objects.filter(
            playlistId=playlist, trackId=track
        ).exists():
            return Response(
                {"detail": "Track already in this playlist."},
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            max_pos = (
                models.PlaylistTrack.objects.filter(playlistId=playlist)
                .aggregate(m=Max("position"))["m"]
                or 0
            )
            pt = models.PlaylistTrack.objects.create(
                playlistId=playlist,
                trackId=track,
                position=max_pos + 1,
                selectionReason=models.PlaylistTrack.SelectionReason.TAG_MATCH,
            )
            models.Playlist.objects.filter(pk=playlist.pk).update(
                trackCount=max_pos + 1
            )

        return Response(
            serializers.PlaylistTrackSerializer(pt).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="remove-track",
        permission_classes=[IsAuthenticated],
    )
    def remove_track(self, request, pk=None):
        """Remove a track from a user-owned saved playlist and reflow positions."""
        playlist = self.get_object()

        if not models.SavedPlaylist.objects.filter(
            userId=request.user, playlistId=playlist
        ).exists():
            return Response(
                {"detail": "You can only remove tracks from playlists you've saved."},
                status=status.HTTP_403_FORBIDDEN,
            )

        track_id = request.data.get("trackId")
        if not track_id:
            return Response({"detail": "trackId is required."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                pt = models.PlaylistTrack.objects.select_for_update().get(
                    playlistId=playlist, trackId_id=track_id,
                )
            except models.PlaylistTrack.DoesNotExist:
                return Response({"detail": "Track is not in this playlist."}, status=status.HTTP_404_NOT_FOUND)

            removed_pos = pt.position
            pt.delete()

            # Reflow remaining positions so they stay contiguous (1..N).
            models.PlaylistTrack.objects.filter(
                playlistId=playlist, position__gt=removed_pos,
            ).update(position=F("position") - 1)

            new_count = models.PlaylistTrack.objects.filter(playlistId=playlist).count()
            models.Playlist.objects.filter(pk=playlist.pk).update(trackCount=new_count)

        return Response(status=status.HTTP_204_NO_CONTENT)

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

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("playlistId")
        )

    def get_permissions(self):
        # Rename (PATCH/PUT) and delete must be authenticated; ownership is
        # enforced in the methods below.
        if self.action in {"update", "partial_update", "destroy"}:
            return [IsAuthenticated()]
        return super().get_permissions()

    def _assert_owner(self, instance, request):
        if instance.userId_id != request.user.id:
            raise PermissionDenied("You can only modify your own playlists.")

    def update(self, request, *args, **kwargs):
        self._assert_owner(self.get_object(), request)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self._assert_owner(self.get_object(), request)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._assert_owner(self.get_object(), request)
        return super().destroy(request, *args, **kwargs)

    @action(
        detail=False,
        methods=["get"],
        url_path="mine",
        permission_classes=[IsAuthenticated],
    )
    def mine(self, request):
        """List the current user's saved playlists, newest first."""
        qs = (
            self.get_queryset()
            .filter(userId=request.user)
            .order_by("-updatedAt")
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)




_SAAVN_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.jiosaavn.com/',
}

_DES_KEY = b'38346591'

# Reject JioSaavn matches below this title/artist confidence so a wrong song is
# never served — the player skips the track instead (see MusicPlayer.jsx).
# Mirrors the audio engine's match gate (tracks/analysis/audio_source.py).
_SAAVN_MIN_MATCH = 0.5


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
        return set(re.sub(r'[^\w\s]', ' ', (text or '').lower()).split())

    def _contained(query_words, target_words):
        """Fraction of query_words present in target_words (asymmetric, 0-1)."""
        if not query_words:
            return 0.0
        return len(query_words & target_words) / len(query_words)

    def _result_language(result):
        return (result.get('language') or '').strip().lower()

    def _score_result(result, target_title_words, target_artist_words):
        # Asymmetric containment: how much of the *requested* title/artist the
        # candidate covers. Robust to JioSaavn's longer official titles, and
        # (unlike raw overlap) it never rewards a candidate just for being short.
        song_title = result.get('song') or result.get('title') or ''
        title_score = _contained(target_title_words, _words(song_title))
        if not target_artist_words:
            return title_score
        song_artist = result.get('primary_artists') or result.get('singers') or ''
        artist_score = _contained(target_artist_words, _words(song_artist))
        return 0.6 * title_score + 0.4 * artist_score

    def _best_match(candidates, target_title_words, target_artist_words,
                    target_language=''):
        # Drop cross-language collisions first: JioSaavn often has several songs
        # sharing a title across languages (e.g. a Hindi "Gondhal" alongside the
        # Marathi one). Without this a Marathi track can play a Hindi recording.
        if target_language:
            same_lang = [c for c in candidates
                         if not _result_language(c)
                         or _result_language(c) == target_language]
            if same_lang:  # only narrow when something is left to match
                candidates = same_lang
        if not candidates:
            return None
        scored = [(c, _score_result(c, target_title_words, target_artist_words))
                  for c in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        best, best_score = scored[0]
        # Below the gate it's almost certainly the wrong song; return nothing so
        # the caller 404s and the player skips, rather than serving garbage.
        if best_score < _SAAVN_MIN_MATCH:
            return None
        return best

    # Determine what to match against — prefer DB title/artist over raw query
    if track:
        _target_title = track.title or query
        _target_artist = track.artistId.name if track.artistId else ''
        _target_language = (track.language or '').strip().lower()
    else:
        _target_title = query
        _target_artist = ''
        _target_language = ''

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

        song = _best_match(unique, _title_words, _artist_words, _target_language)

        # Fallback: if nothing cleared the gate, retry with a trimmed query
        # (drops a trailing artist word) but keep the same confidence gate.
        if not song and ' ' in query:
            short = query.rsplit(' ', 1)[0]
            song = _best_match(_fetch_songs(short), _title_words, _artist_words,
                               _target_language)

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
