from django.contrib import admin
from .models import TrackFeedback, UserMoodPreference, TrackMoodScore


@admin.register(TrackFeedback)
class TrackFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'userId',
        'trackId',
        'playlistId',
        'playlistTrackId',
        'moodSessionId',
        'action',
        'listenProgress',
        'moodLabel',
    )


@admin.register(UserMoodPreference)
class UserMoodPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'userId',
        'moodLabel',
        'songWeight',
        'instrumentalWeight',
        'ambientWeight',
        'noveltyScore',
        'sampleCount',
        'lastComputedAt',
    )


@admin.register(TrackMoodScore)
class TrackMoodScoreAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'userId',
        'trackId',
        'moodLabel',
        'score',
        'likeCount',
        'dislikeCount',
        'skipCount',
        'completeCount',
        'lastUpdatedAt',
    )


# Register your models here.
