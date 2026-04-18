from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from harmonic_navigator.views import HarmonicBaseViewSet
from . import models, serializers, filters
from .services import start_session, submit_answers


class MoodSessionViewSet(HarmonicBaseViewSet):
    queryset = models.MoodSession.objects.all()
    serializer_class = serializers.MoodSessionSerializer
    filterset_class = filters.MoodSessionFilter
    permission_classes = (AllowAny,)
    search_fields = ()
    ordering_fields = ("createdAt", "updatedAt")

    def create(self, request, *args, **kwargs):

        session = start_session(user=request.user)
        return Response(
            self.get_serializer(session).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):

        session = self.get_object()

        if session.endedAt is not None:
            return Response(
                {"detail": "This session has already been submitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if session.userId and session.userId != request.user:
            return Response(
                {"detail": "Not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = serializers.SubmitAnswersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            inference = submit_answers(
                session=session,
                answers=serializer.validated_data["answers"],
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            serializers.MoodInferenceSerializer(
                inference,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous:
            # Allow seeing guest sessions created by anonymous users
            return super().get_queryset().filter(userId__isnull=True)
        return super().get_queryset().filter(userId=user)


class QuestionViewSet(HarmonicBaseViewSet):
    queryset = models.Question.objects.all()
    serializer_class = serializers.QuestionSerializer
    filterset_class = filters.QuestionFilter
    permission_classes = (AllowAny,)
    search_fields = ()
    ordering_fields = ("createdAt", "updatedAt", "order")

    def get_queryset(self):
        """
        Default list only returns active questions ordered for the wizard.
        Pass ?isActive=false to see retired questions as well.
        """
        qs = super().get_queryset()
        if self.request.query_params.get("isActive") != "false":
            qs = qs.filter(isActive=True)
        return qs.order_by("order")


class AnswerViewSet(HarmonicBaseViewSet):
    queryset = models.Answer.objects.all()
    serializer_class = serializers.AnswerSerializer
    filterset_class = filters.AnswerFilter
    permission_classes = (IsAuthenticated,)
    search_fields = ()
    ordering_fields = ("createdAt", "updatedAt")

    def get_queryset(self):
        """Answers are always scoped to the requesting user's sessions."""
        return (
            super().get_queryset()
            .filter(moodSessionId__userId=self.request.user)
            .select_related("moodSessionId", "questionId")
        )


class MoodInferenceViewSet(HarmonicBaseViewSet):
    queryset = models.MoodInference.objects.all()
    serializer_class = serializers.MoodInferenceSerializer
    filterset_class = filters.MoodInferenceFilter
    permission_classes = (IsAuthenticated,)
    search_fields = ()
    ordering_fields = ("createdAt", "updatedAt", "confidence")

    def get_queryset(self):
        """Inferences are always scoped to the requesting user's sessions."""
        return (
            super().get_queryset()
            .filter(moodSessionId__userId=self.request.user)
            .select_related("moodSessionId")
        )
