from harmonic_navigator.views import HarmonicBaseViewSet

from .models import MusicTrack
from .serializers import MusicTrackSerializer
from .filters import MusicTrackFilterSet


class MusicTrackViewSet(HarmonicBaseViewSet):
    queryset = MusicTrack.objects.all()
    serializer_class = MusicTrackSerializer
    filterset_class = MusicTrackFilterSet
    permission_classes = []
    search_fields = ()
    ordering_fields = (
        "createdAt",
        "updatedAt",
    )
