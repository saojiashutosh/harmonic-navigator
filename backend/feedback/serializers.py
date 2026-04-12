from harmonic_navigator.serializers import HarmonicBaseSerializer
from .models import TrackFeedback, UserMoodPreference, TrackMoodScore


class TrackFeedbackSerializer(HarmonicBaseSerializer):

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
            'listenProgress',
            'moodLabel',
        )


class UserMoodPreferenceSerializer(HarmonicBaseSerializer):

    class Meta:
        model = UserMoodPreference
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'userId',
            'moodLabel',
            'songWeight',
            'instrumentalWeight',
            'ambientWeight',
            'noveltyScore',
            'sampleCount',
            'lastComputedAt',
        )


class TrackMoodScoreSerializer(HarmonicBaseSerializer):

    class Meta:
        model = TrackMoodScore
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'userId',
            'trackId',
            'moodLabel',
            'score',
            'likeCount',
            'dislikeCount',
            'skipCount',
            'completeCount',
            'lastUpdatedAt',
        )
