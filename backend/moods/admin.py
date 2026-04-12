from django.contrib import admin
from .models import MoodSession, Question, Answer, MoodInference


@admin.register(MoodSession)
class MoodSessionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'userId',
        'startedAt',
        'endedAt',
        "durationSeconds",
    )


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
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


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        "moodSessionId",
        "questionId",
        "rawValue",
        "value",
    )


@admin.register(MoodInference)
class MoodInferenceAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        "moodSessionId",
        "moodLabel",
        "confidence",
        "rawScores",
    )
