from django.contrib import admin

from .models import ConcertEvent, ConcertPlaylist


@admin.register(ConcertEvent)
class ConcertEventAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'artistId',
        'name',
        'venueName',
        'city',
        'country',
        'eventDate',
        'source',
        'isActive',
    )


@admin.register(ConcertPlaylist)
class ConcertPlaylistAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'createdAt',
        'updatedAt',
        'concertEventId',
        'playlistId',
        'userId',
        'city',
    )
