from django.contrib import admin
from .models import TrackFeedback, UserMoodPreference, TrackMoodScore


@admin.register(TrackFeedback)
class TrackFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'user',
        'track',
        'playlist',
        'playlist_track',
        'mood_session',
        'action',
        'listen_progress',
        'mood_label',
    )


@admin.register(UserMoodPreference)
class UserMoodPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'user',
        'mood_label',
        'song_weight',
        'instrumental_weight',
        'ambient_weight',
        'novelty_score',
        'sample_count',
        'last_computed_at',
    )


@admin.register(TrackMoodScore)
class TrackMoodScoreAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'user',
        'track',
        'mood_label',
        'score',
        'like_count',
        'dislike_count',
        'skip_count',
        'complete_count',
        'last_updated_at',
    )


# Register your models here.
