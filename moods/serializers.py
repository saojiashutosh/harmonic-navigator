from harmonic_navigator.serializers import HarmonicBaseSerializer
from .models import (
    MoodSession,
    Question,
    Answer,
    MoodInference,
)


class MoodSessionSerializer(HarmonicBaseSerializer):

    class Meta:
        model = MoodSession
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'userId',
            'startedAt',
            'endedAt',
            "durationSeconds",
        )


class QuestionSerializer(HarmonicBaseSerializer):

    class Meta:
        model = Question
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            "key",
            'text',
            'category',
            'inputType',
            'options',
            "order",
            "isActive",
        )


class AnswerSerializer(HarmonicBaseSerializer):

    class Meta:
        model = Answer
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            "moodSessionId",
            "questionId",
            "rawValue",
            "value",
        )


class MoodInferenceSerializer(HarmonicBaseSerializer):

    class Meta:
        model = MoodInference
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            "moodSessionId",
            "moodLabel",
            "confidence",
            "rawScores",
        )
