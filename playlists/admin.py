from django.contrib import admin
from .models import Playlist, PlaylistTrack, SavedPlaylist


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'userId',
        'moodInferenceId',
        'moodLabel',
        'confidence',
        'status',
        'isSaved',
        'savedAt',
        'trackCount',
    )


@admin.register(PlaylistTrack)
class PlaylistTrackAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'playlistId',
        'trackId',
        'position',
        'selectionReason',
        'relevanceScore',
        'playState',
        'playedAt',
    )


@admin.register(SavedPlaylist)
class SavedPlaylistAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'userId',
        'playlistId',
        'name',
    )


# Register your models here.
