from django.contrib import admin
from .models import MoodTag, Artist, Track, TrackMoodTag, AudioFeatureSnapshot


@admin.register(MoodTag)
class MoodTagAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'name',
        'mood',
        'color',
    )


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'name',
        'spotify_id',
    )


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'title',
        'artist',
        'type',
        'source',
        'spotify_id',
        'tempo_bpm',
        'duration_ms',
        'is_active',
    )


@admin.register(TrackMoodTag)
class TrackMoodTagAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'track',
        'mood_tag',
        'weight',
        'tag_source',
    )


@admin.register(AudioFeatureSnapshot)
class AudioFeatureSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'track',
        'synced_at',
    )


# Register your models here.
