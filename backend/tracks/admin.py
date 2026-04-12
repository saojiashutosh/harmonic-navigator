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
        'spotifyId',
    )


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'title',
        'artistId',
        'type',
        'source',
        'spotifyId',
        'tempoBpm',
        'durationMs',
        'isActive',
    )


@admin.register(TrackMoodTag)
class TrackMoodTagAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'trackId',
        'moodTagId',
        'weight',
        'tagSource',
    )


@admin.register(AudioFeatureSnapshot)
class AudioFeatureSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'trackId',
        'syncedAt',
    )


# Register your models here.
