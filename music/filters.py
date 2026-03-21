from harmonic_navigator.filters import HarmonicDateFilter

from .models import MusicTrack


class MusicTrackFilterSet(HarmonicDateFilter):
    class Meta:
        model = MusicTrack
        fields = (
            "createdAt",
            "updatedAt",
            "title",
            "artist",
            "album",
            "duration",
        )
