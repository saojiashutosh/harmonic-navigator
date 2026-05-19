from rest_framework import serializers

from harmonic_navigator.serializers import HarmonicBaseSerializer
from playlists.serializers import PlaylistSerializer

from .models import ConcertEvent, ConcertPlaylist


class ConcertEventSerializer(HarmonicBaseSerializer):
    artistName = serializers.CharField(source="artistId.name", read_only=True)

    class Meta:
        model = ConcertEvent
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'artistId',
            'artistName',
            'externalId',
            'name',
            'venueName',
            'city',
            'country',
            'eventDate',
            'ticketUrl',
            'imageUrl',
            'recentSetlist',
            'source',
            'isActive',
        )


class ConcertPlaylistSerializer(HarmonicBaseSerializer):
    playlist = PlaylistSerializer(source="playlistId", read_only=True)
    concertEvent = ConcertEventSerializer(source="concertEventId", read_only=True)

    class Meta:
        model = ConcertPlaylist
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'concertEventId',
            'concertEvent',
            'playlistId',
            'playlist',
            'userId',
            'city',
        )


class DiscoverConcertsSerializer(serializers.Serializer):
    city = serializers.CharField(max_length=128)


class GenerateConcertPlaylistSerializer(serializers.Serializer):
    limit = serializers.IntegerField(
        required=False, min_value=1, max_value=60, default=25,
    )
