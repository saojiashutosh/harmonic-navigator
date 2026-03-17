from django.shortcuts import render
from . import models, serailizers, filters
from harmonic_navigator.views import HarmonicBaseViewSet


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
