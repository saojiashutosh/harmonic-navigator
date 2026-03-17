from django.contrib import admin
from .models import Playlist, PlaylistTrack, SavedPlaylist


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'user',
        'mood_inference',
        'mood_label',
        'confidence',
        'status',
        'is_saved',
        'saved_at',
        'track_count',
    )


@admin.register(PlaylistTrack)
class PlaylistTrackAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'playlist',
        'track',
        'position',
        'selection_reason',
        'relevance_score',
        'play_state',
        'played_at',
    )


@admin.register(SavedPlaylist)
class SavedPlaylistAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'user',
        'playlist',
        'name',
    )


# Register your models here.
