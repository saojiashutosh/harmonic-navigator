from harmonic_navigator.filters import HarmonicBaseFilterSet
from .models import (
    MoodSession,
    Question,
    Answer,
    MoodInference,
)


class MoodSessionFilter(HarmonicBaseFilterSet):
    class Meta:
        model = MoodSession
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'userId',
            'startedAt',
            'endedAt',
        )


class QuestionFilter(HarmonicBaseFilterSet):
    class Meta:
        model = Question
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'category',
            'inputType',
            "order",
            "isActive",
        )


class AnswerFilter(HarmonicBaseFilterSet):
    class Meta:
        model = Answer
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            "moodSessionId",
            "questionId",
        )


class MoodInferenceFilter(HarmonicBaseFilterSet):
    class Meta:
        model = MoodInference
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            "moodSessionId",
            "moodLabel",
            "confidence",
        )
