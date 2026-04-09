from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from . import models, serailizers, filters
from harmonic_navigator.views import HarmonicBaseViewSet
from .services import import_spotify_search_results
from .spotify_client import SpotifyConfigurationError, SpotifyImportError


class MoodTagView(HarmonicBaseViewSet):
    queryset = models.MoodTag.objects.all()
    serializer_class = serailizers.MoodTagSerializer
    filterset_class = filters.MoodTagFilter
    # permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'createdAt',
        'updatedAt',
        'name',
    )


class ArtistView(HarmonicBaseViewSet):
    queryset = models.Artist.objects.all()
    serializer_class = serailizers.ArtistSerializer
    filterset_class = filters.ArtistFilter
    # permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'createdAt',
        'updatedAt',
        'name',
    )


class TrackView(HarmonicBaseViewSet):
    queryset = models.Track.objects.all()
    serializer_class = serailizers.TrackSerializer
    filterset_class = filters.TrackFilter
    # permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'createdAt',
        'updatedAt',
        'tempoBpm',
        'durationMs',
        'energy',
        'valence',
    )

    @action(detail=False, methods=["post"], url_path="import-spotify")
    def import_spotify(self, request):
        serializer = serailizers.SpotifyImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            tracks = import_spotify_search_results(
                query=serializer.validated_data["query"],
                limit=serializer.validated_data["limit"],
                market=serializer.validated_data.get("market"),
            )
        except SpotifyConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except SpotifyImportError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {
                "count": len(tracks),
                "tracks": self.get_serializer(tracks, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )


class TrackMoodTagView(HarmonicBaseViewSet):
    queryset = models.TrackMoodTag.objects.all()
    serializer_class = serailizers.TrackMoodTagSerializer
    filterset_class = filters.TrackMoodTagFilter
    # permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'createdAt',
        'updatedAt',
        'weight',
    )


class AudioFeatureSnapshotView(HarmonicBaseViewSet):
    queryset = models.AudioFeatureSnapshot.objects.all()
    serializer_class = serailizers.AudioFeatureSnapshotSerializer
    filterset_class = filters.AudioFeatureSnapshotFilter
    # permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'createdAt',
        'updatedAt',
        'syncedAt',
    )
