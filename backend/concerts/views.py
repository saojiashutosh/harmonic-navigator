from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from harmonic_navigator.views import HarmonicBaseViewSet
from helpers.allevents_client import AllEventsScrapeError
from helpers.setlistfm_client import SetlistFmRequestError

from . import filters, models, serializers
from .services import build_concert_playlist, dedupe_concerts, discover_concerts


class ConcertEventViewSet(HarmonicBaseViewSet):
    queryset = models.ConcertEvent.objects.select_related("artistId").all()
    serializer_class = serializers.ConcertEventSerializer
    filterset_class = filters.ConcertEventFilter
    permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'createdAt',
        'updatedAt',
        'eventDate',
    )

    @action(detail=False, methods=["post"], url_path="discover")
    def discover(self, request):
        """Discover upcoming concerts in a city for catalog artists.

        Scrapes AllEvents in real time, then returns every active concert
        stored for the city — so manually-entered events (source='manual')
        always show even if the live scrape fails.
        """
        serializer = serializers.DiscoverConcertsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        city = serializer.validated_data["city"]

        api_error = None
        try:
            discover_concerts(city)
        except AllEventsScrapeError as exc:
            # Live scrape failed — fall back to concerts already on file.
            api_error = str(exc)

        # dedupe_concerts collapses any duplicate listings (same artist,
        # venue and date) — including rows stored before discovery learned
        # to skip them.
        events = dedupe_concerts(
            models.ConcertEvent.objects
            .select_related("artistId")
            .filter(city__icontains=city, isActive=True)
            .order_by("eventDate")
        )
        data = serializers.ConcertEventSerializer(
            events, many=True, context=self.get_serializer_context(),
        ).data
        return Response({
            "city": city,
            "count": len(data),
            "events": data,
            "apiError": api_error,
        })

    @action(detail=True, methods=["post"], url_path="generate-playlist")
    def generate_playlist(self, request, pk=None):
        """Generate a setlist-weighted concert-prep playlist for an event."""
        event = self.get_object()
        serializer = serializers.GenerateConcertPlaylistSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        limit = serializer.validated_data["limit"]

        try:
            concert_playlist = build_concert_playlist(
                event, limit=limit, user=request.user,
            )
        except SetlistFmRequestError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            serializers.ConcertPlaylistSerializer(
                concert_playlist, context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )


class ConcertPlaylistViewSet(HarmonicBaseViewSet):
    queryset = models.ConcertPlaylist.objects.select_related(
        "concertEventId",
        "concertEventId__artistId",
        "playlistId",
    ).all()
    serializer_class = serializers.ConcertPlaylistSerializer
    filterset_class = filters.ConcertPlaylistFilter
    permission_classes = ()
    search_fields = ()
    ordering_fields = (
        'createdAt',
        'updatedAt',
    )
