from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from harmonic_navigator.views import HarmonicBaseViewSet
from moods.models import MoodSession

from . import filters, models, serializers, services


class GroupSessionViewSet(HarmonicBaseViewSet):
    """Endpoints for the group listening flow.

    A short walkthrough:
      - host calls POST /groups/group-sessions/        to spin up a room
      - others call POST /groups/group-sessions/join/  with the code
      - each participant takes the regular mood survey (moods app)
      - frontend calls POST /groups/group-sessions/{id}/attach-session/
        once a participant's MoodInference exists, flipping isReady=True
      - host polls GET /groups/group-sessions/{id}/    to see who's ready
      - host calls POST /groups/group-sessions/{id}/generate/ which blends
        the inferences, builds a shared playlist, returns it
    """

    queryset = models.GroupSession.objects.all()
    serializer_class = serializers.GroupSessionSerializer
    filterset_class = filters.GroupSessionFilter
    permission_classes = (AllowAny,)
    search_fields = ()
    ordering_fields = ('createdAt', 'updatedAt')

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("playlistId", "hostId")
            .prefetch_related("participants__moodSessionId__mood_inference")
        )

    def create(self, request, *args, **kwargs):
        """Host creates a room. Body: {displayName}."""
        serializer = serializers.CreateGroupSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session, host = services.create_group(
            host_user=request.user,
            host_display_name=serializer.validated_data["displayName"],
        )
        return Response(
            {
                "groupSession": self.get_serializer(session).data,
                "participantId": str(host.id),
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="join")
    def join(self, request):
        """Joiner enters the code. Body: {code, displayName}."""
        serializer = serializers.JoinGroupSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            session, participant = services.join_group(
                code=serializer.validated_data["code"],
                user=request.user,
                display_name=serializer.validated_data["displayName"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "groupSession": self.get_serializer(session).data,
                "participantId": str(participant.id),
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="attach-session")
    def attach_session(self, request, pk=None):
        """Link a participant's completed MoodSession to the group."""
        group = self.get_object()
        serializer = serializers.AttachMoodSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            participant = group.participants.get(
                id=serializer.validated_data["participantId"]
            )
        except models.GroupParticipant.DoesNotExist:
            return Response({"detail": "Participant not in this group."}, status=status.HTTP_404_NOT_FOUND)

        try:
            mood_session = MoodSession.objects.get(
                id=serializer.validated_data["moodSessionId"]
            )
        except MoodSession.DoesNotExist:
            return Response({"detail": "Mood session not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            services.attach_mood_session(
                group=group,
                participant=participant,
                mood_session=mood_session,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.get_serializer(group).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="generate")
    def generate(self, request, pk=None):
        """Host blends ready participants and builds the shared playlist."""
        group = self.get_object()
        try:
            services.generate_group_playlist(group)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        group.refresh_from_db()
        return Response(self.get_serializer(group).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="by-code/(?P<code>[A-Za-z0-9]+)")
    def by_code(self, request, code=None):
        """Look up a group session by its join code (used by the join screen)."""
        try:
            session = self.get_queryset().get(code=(code or "").upper())
        except models.GroupSession.DoesNotExist:
            return Response({"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(session).data)
