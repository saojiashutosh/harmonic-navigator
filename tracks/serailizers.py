from rest_framework import serializers

from harmonic_navigator.serializers import HarmonicBaseSerializer
from .models import (
    MoodTag,
    Artist,
    Track,
    TrackMoodTag,
    AudioFeatureSnapshot,
)


class MoodTagSerializer(HarmonicBaseSerializer):

    class Meta:
        model = MoodTag
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'name',
            'mood',
            'color',
        )


class ArtistSerializer(HarmonicBaseSerializer):

    class Meta:
        model = Artist
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'name',
            'spotifyId',
        )


class TrackSerializer(HarmonicBaseSerializer):
    durationMinutes = serializers.CharField(source="duration_minutes", read_only=True)

    class Meta:
        model = Track
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'title',
            'artistId',
            'type',
            'source',
            'spotifyId',
            'fmaId',
            'previewUrl',
            'externalUrl',
            'tempoBpm',
            'durationMs',
            'durationMinutes',
            'keySignature',
            'energy',
            'valence',
            'acousticness',
            'instrumentalness',
            'loudness',
            'primaryMood',
            'isInstrumental',
            'isExplicit',
            'isActive',
            'featuresSyncedAt',
        )


class SpotifyImportSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=255)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=20)
    market = serializers.CharField(required=False, max_length=2, allow_blank=False)


class TrackMoodTagSerializer(HarmonicBaseSerializer):

    class Meta:
        model = TrackMoodTag
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'trackId',
            'moodTagId',
            'weight',
            'tagSource',
        )


class AudioFeatureSnapshotSerializer(HarmonicBaseSerializer):

    class Meta:
        model = AudioFeatureSnapshot
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'trackId',
            'snapshot',
            'syncedAt',
        )
