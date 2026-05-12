from django.core.cache import cache
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from harmonic_navigator.views import HarmonicBaseViewSet
from helpers.cache_utils import QUESTIONS_CACHE_KEY, QUESTIONS_TTL
from . import models, serializers, filters
from .services import start_session, submit_answers

_GUEST_MAX_SURVEYS = 2
_SESSION_KEY = "anonymous_survey_count"


class MoodSessionViewSet(HarmonicBaseViewSet):
    queryset = models.MoodSession.objects.all()
    serializer_class = serializers.MoodSessionSerializer
    filterset_class = filters.MoodSessionFilter
    permission_classes = (AllowAny,)
    search_fields = ()
    ordering_fields = ("createdAt", "updatedAt")

    def create(self, request, *args, **kwargs):
        if request.user.is_anonymous:
            count = request.session.get(_SESSION_KEY, 0)
            if count >= _GUEST_MAX_SURVEYS:
                return Response(
                    {
                        "detail": "You've used your 2 free surveys. Please log in to continue.",
                        "code": "GUEST_LIMIT_REACHED",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        session = start_session(user=request.user)

        if request.user.is_anonymous:
            request.session[_SESSION_KEY] = request.session.get(_SESSION_KEY, 0) + 1
            request.session.modified = True

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
        qs = super().get_queryset()
        if self.request.query_params.get("isActive") != "false":
            qs = qs.filter(isActive=True)
        return qs.order_by("order")

    def list(self, request, *args, **kwargs):
        # Serve cached response for the standard active-questions request
        # (the wizard loads this on every page visit).
        if request.query_params.get("isActive") != "false":
            cached = cache.get(QUESTIONS_CACHE_KEY)
            if cached is not None:
                return Response(cached)
            response = super().list(request, *args, **kwargs)
            cache.set(QUESTIONS_CACHE_KEY, response.data, QUESTIONS_TTL)
            return response
        return super().list(request, *args, **kwargs)


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
