from harmonic_navigator.serializers import HarmonicBaseSerializer
from .models import Playlist, PlaylistTrack, SavedPlaylist


class PlaylistSerializer(HarmonicBaseSerializer):

    class Meta:
        model = Playlist
        fields = (
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


class PlaylistTrackSerializer(HarmonicBaseSerializer):

    class Meta:
        model = PlaylistTrack
        fields = (
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


class SavedPlaylistSerializer(HarmonicBaseSerializer):

    class Meta:
        model = SavedPlaylist
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'userId',
            'playlistId',
            'name',
        )
