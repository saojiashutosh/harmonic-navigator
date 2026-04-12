from harmonic_navigator.filters import HarmonicBaseFilterSet
from .models import Playlist, PlaylistTrack, SavedPlaylist


class PlaylistFilter(HarmonicBaseFilterSet):
    class Meta:
        model = Playlist
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'userId',
            'moodInferenceId',
            'moodLabel',
            'status',
            'isSaved',
        )


class PlaylistTrackFilter(HarmonicBaseFilterSet):
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
            'playState',
        )


class SavedPlaylistFilter(HarmonicBaseFilterSet):
    class Meta:
        model = SavedPlaylist
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'userId',
            'playlistId',
        )
