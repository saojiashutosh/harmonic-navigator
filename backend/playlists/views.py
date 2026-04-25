from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from harmonic_navigator.views import HarmonicBaseViewSet
from moods.models import MoodSession

from . import filters, models, serializers
from .services import build_playlist_for_session


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

        try:
            playlist = build_playlist_for_session(
                session,
                limit=serializer.validated_data["limit"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            self.get_serializer(playlist).data,
            status=status.HTTP_201_CREATED,
        )


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


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
import requests
import re
import urllib.parse

@api_view(['GET'])
@permission_classes([AllowAny])
def youtube_search(request):
    query = request.query_params.get('q', '')
    if not query:
        return Response({"error": "Query parameter 'q' is required."}, status=status.HTTP_400_BAD_REQUEST)
    
    q = urllib.parse.quote(query)
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(f'https://www.youtube.com/results?search_query={q}', headers=headers, timeout=5)
        match = re.search(r'\"videoId\":\"([a-zA-Z0-9_-]{11})\"', res.text)
        if match:
            return Response({"videoId": match.group(1)})
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    return Response({"error": "No video found."}, status=status.HTTP_404_NOT_FOUND)


# Create your views here.
