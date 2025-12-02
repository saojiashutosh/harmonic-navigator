from music.models import MusicTrack
from harmonic_navigator.serializers import HarmonicBaseSerializer
# from rest_framework import serializers


class MusicTrackSerializer(HarmonicBaseSerializer):
    class Meta:
        model = MusicTrack
        fields = [
            'id',
            'title',
            'artist',
            'album',
            'duration',
            'createdAt',
            'updatedAt',
        ]
