from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from harmonic_navigator.views import HarmonicBaseViewSet
from helpers.setlistfm_client import SetlistFmRequestError
from helpers.ticketmaster_client import (
    TicketmasterConfigurationError,
    TicketmasterRequestError,
)

from . import filters, models, serializers
from .services import build_concert_playlist, discover_concerts


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
        """Discover upcoming concerts in a city for catalog artists."""
        serializer = serializers.DiscoverConcertsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        city = serializer.validated_data["city"]
        country_code = serializer.validated_data.get("countryCode") or None

        try:
            events = discover_concerts(city, country_code=country_code)
        except TicketmasterConfigurationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except TicketmasterRequestError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = serializers.ConcertEventSerializer(
            events, many=True, context=self.get_serializer_context(),
        ).data
        return Response({"city": city, "count": len(events), "events": data})

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
