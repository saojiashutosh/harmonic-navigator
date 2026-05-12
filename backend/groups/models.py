from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from harmonic_navigator.models import HarmonicBaseModel


class GroupSession(HarmonicBaseModel):
    """A shared listening session that blends the moods of multiple people.

    One person creates a session (the host) and others join via the 6-char
    code. Each participant takes their own mood survey on their own device,
    and once enough participants are ready the host generates a single
    blended playlist for the whole group.
    """

    class StatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"        # waiting for participants
        GENERATED = "generated", "Generated"  # blended playlist ready
        CLOSED = "closed", "Closed"           # host closed the room

    code = models.CharField(
        max_length=8,
        unique=True,
        verbose_name=_("Join Code"),
        db_column="code",
    )

    hostId = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="hosted_group_sessions",
        db_column="host_id",
        verbose_name=_("Host"),
    )

    status = models.CharField(
        max_length=16,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
        verbose_name=_("Status"),
        db_column="status",
    )

    playlistId = models.ForeignKey(
        "playlists.Playlist",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="group_sessions",
        db_column="playlist_id",
        verbose_name=_("Group Playlist"),
    )

    blendedMoodLabel = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        verbose_name=_("Blended Mood Label"),
        db_column="blended_mood_label",
    )

    expiresAt = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Expires At"),
        db_column="expires_at",
    )

    class Meta:
        db_table = "group_sessions"
        verbose_name = "Group Session"
        verbose_name_plural = "Group Sessions"
        managed = True

    def __str__(self):
        return f"GroupSession {self.code} ({self.status})"


class GroupParticipant(HarmonicBaseModel):
    """One person inside a GroupSession.

    The host gets a row too. `userId` is null for guest joiners. `moodSessionId`
    is attached after that participant submits their own mood survey, which
    is also when `isReady` flips true.
    """

    groupSessionId = models.ForeignKey(
        GroupSession,
        on_delete=models.CASCADE,
        related_name="participants",
        db_column="group_session_id",
        verbose_name=_("Group Session"),
    )

    userId = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="group_participations",
        db_column="user_id",
        verbose_name=_("User"),
    )

    moodSessionId = models.ForeignKey(
        "moods.MoodSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="group_participations",
        db_column="mood_session_id",
        verbose_name=_("Mood Session"),
    )

    displayName = models.CharField(
        max_length=64,
        verbose_name=_("Display Name"),
        db_column="display_name",
    )

    isHost = models.BooleanField(
        default=False,
        verbose_name=_("Is Host"),
        db_column="is_host",
    )

    isReady = models.BooleanField(
        default=False,
        verbose_name=_("Is Ready"),
        db_column="is_ready",
    )

    class Meta:
        db_table = "group_participants"
        verbose_name = "Group Participant"
        verbose_name_plural = "Group Participants"
        managed = True

    def __str__(self):
        return f"{self.displayName} @ {self.groupSessionId_id}"
