from django.shortcuts import render
from . import models, serializers, filters
from harmonic_navigator.views import HarmonicBaseViewSet


class TrackFeedbackViewSet(HarmonicBaseViewSet):
    queryset = models.TrackFeedback.objects.all()
    serializer_class = serializers.TrackFeedbackSerializer
    filterset_class = filters.TrackFeedbackFilter
    permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'createdAt',
        'updatedAt',
    )


class UserMoodPreferenceViewSet(HarmonicBaseViewSet):
    queryset = models.UserMoodPreference.objects.all()
    serializer_class = serializers.UserMoodPreferenceSerializer
    filterset_class = filters.UserMoodPreferenceFilter
    permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'createdAt',
        'updatedAt',
        'lastComputedAt',
    )


class TrackMoodScoreViewSet(HarmonicBaseViewSet):
    queryset = models.TrackMoodScore.objects.all()
    serializer_class = serializers.TrackMoodScoreSerializer
    filterset_class = filters.TrackMoodScoreFilter
    permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'createdAt',
        'updatedAt',
        'score',
    )


# Create your views here.
