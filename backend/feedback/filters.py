from harmonic_navigator.filters import HarmonicBaseFilterSet
from .models import TrackFeedback, UserMoodPreference, TrackMoodScore


class TrackFeedbackFilter(HarmonicBaseFilterSet):
    class Meta:
        model = TrackFeedback
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'userId',
            'trackId',
            'playlistId',
            'playlistTrackId',
            'moodSessionId',
            'action',
            'moodLabel',
        )


class UserMoodPreferenceFilter(HarmonicBaseFilterSet):
    class Meta:
        model = UserMoodPreference
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'userId',
            'moodLabel',
        )


class TrackMoodScoreFilter(HarmonicBaseFilterSet):
    class Meta:
        model = TrackMoodScore
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'userId',
            'trackId',
            'moodLabel',
        )
