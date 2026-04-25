from harmonic_navigator.serializers import HarmonicBaseSerializer
from .models import (
    MoodSession,
    Question,
    Answer,
    MoodInference,
)
from rest_framework import serializers


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
    is_high_confidence = serializers.SerializerMethodField()

    def get_is_high_confidence(self, obj):
        return obj.confidence >= 0.7

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
            "secondaryMoodLabel",
            "secondaryConfidence",
            "moodBlendRatio",
            "is_high_confidence",
        )


class AnswerInputSerializer(serializers.Serializer):
    """Single answer inside a submit payload."""
    question_key = serializers.CharField(max_length=64)
    raw_value = serializers.CharField(max_length=64)


class SubmitAnswersSerializer(serializers.Serializer):

    answers = AnswerInputSerializer(many=True, min_length=1)

    def validate(self, data):
        keys = [a["question_key"] for a in data["answers"]]

        if len(keys) != len(set(keys)):
            duplicates = {k for k in keys if keys.count(k) > 1}
            raise serializers.ValidationError(
                {"answers": f"Duplicate question keys: {duplicates}"}
            )

        active_keys = set(
            Question.objects
            .filter(key__in=keys, isActive=True)
            .values_list("key", flat=True)
        )
        unknown = set(keys) - active_keys
        if unknown:
            raise serializers.ValidationError(
                {"answers": f"Unknown or inactive question keys: {unknown}"}
            )

        return data
