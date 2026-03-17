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
