from django.shortcuts import render
from . import models, serializers, filters
from harmonic_navigator.views import HarmonicBaseViewSet


class MoodSessionViewSet(HarmonicBaseViewSet):
    queryset = models.MoodSession.objects.all()
    serializer_class = serializers.MoodSessionSerializer
    filterset_class = filters.MoodSessionFilter
    permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'createdAt',
        'updatedAt',
    )


class QuestionViewSet(HarmonicBaseViewSet):
    queryset = models.Question.objects.all()
    serializer_class = serializers.QuestionSerializer
    filterset_class = filters.QuestionFilter
    permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'createdAt',
        'updatedAt',
        "order",
    )


class AnswerViewSet(HarmonicBaseViewSet):
    queryset = models.Answer.objects.all()
    serializer_class = serializers.AnswerSerializer
    filterset_class = filters.AnswerFilter
    permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'createdAt',
        'updatedAt',
    )


class MoodInferenceViewSet(HarmonicBaseViewSet):
    queryset = models.MoodInference.objects.all()
    serializer_class = serializers.MoodInferenceSerializer
    filterset_class = filters.MoodInferenceFilter
    permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'createdAt',
        'updatedAt',
        "confidence",
    )
