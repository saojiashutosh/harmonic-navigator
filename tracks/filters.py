from harmonic_navigator.filters import HarmonicBaseFilterSet
from .models import (
    MoodTag,
    Artist,
    Track,
    TrackMoodTag,
    AudioFeatureSnapshot,
)


class MoodTagFilter(HarmonicBaseFilterSet):
    class Meta:
        model = MoodTag
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'name',
            'mood',
        )


class ArtistFilter(HarmonicBaseFilterSet):
    class Meta:
        model = Artist
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'name',
            'spotifyId',
        )


class TrackFilter(HarmonicBaseFilterSet):
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
            'tempoBpm',
            'durationMs',
            'primaryMood',
            'language',
            'genre',
            'region',
            'ragaName',
            'classicalForm',
            'isInstrumental',
            'isExplicit',
            'isActive',
        )


class TrackMoodTagFilter(HarmonicBaseFilterSet):
    class Meta:
        model = TrackMoodTag
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'trackId',
            'moodTagId',
            'tagSource',
        )


class AudioFeatureSnapshotFilter(HarmonicBaseFilterSet):
    class Meta:
        model = AudioFeatureSnapshot
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'trackId',
            'syncedAt',
        )
