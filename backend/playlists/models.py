from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from harmonic_navigator.models import HarmonicBaseModel


class Playlist(HarmonicBaseModel):
    class StatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    userId = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="playlists",
        db_column="user_id",
        verbose_name=_("user"),
        null=True,
    )

    moodInferenceId = models.ForeignKey(
        "moods.MoodInference",
        on_delete=models.SET_NULL,
        null=True,
        related_name="playlists",
        db_column="mood_inference_id",
        verbose_name=_("mood inference"),
    )

    moodLabel = models.CharField(
        max_length=32,
        verbose_name=_("mood label"),
        db_column="mood_label",
        null=True,
    )
    confidence = models.FloatField(
        verbose_name=_("confidence"),
        db_column="confidence",
        null=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    status = models.CharField(
        max_length=16,
        verbose_name=_("status"),
        db_column="status",
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
    )

    isSaved = models.BooleanField(
        verbose_name=_("is saved"),
        db_column="is_saved",
        default=False,
    )
    savedAt = models.DateTimeField(
        verbose_name=_("saved at"),
        db_column="saved_at",
        null=True,
        blank=True,
    )

    trackCount = models.PositiveSmallIntegerField(
        verbose_name=_("track count"),
        db_column="track_count",
        default=0,
    )

    class Meta:
        db_table = "playlists"
        verbose_name = "Playlist"
        verbose_name_plural = "Playlists"
        managed = True

    def __str__(self):
        return f"{self.moodLabel} playlist - {self.userId} ({self.status})"


class PlaylistTrack(HarmonicBaseModel):
    class SelectionReason(models.TextChoices):
        MOOD_MATCH = "mood_match", "Mood Match"
        TAG_MATCH = "tag_match", "Tag Match"
        NOVELTY = "novelty", "Novelty"
        FALLBACK = "fallback", "Fallback"

    class PlayState(models.TextChoices):
        QUEUED = "queued", "Queued"
        PLAYED = "played", "Played"
        SKIPPED = "skipped", "Skipped"

    playlistId = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name="playlist_tracks",
        db_column="playlist_id",
        verbose_name=_("playlist"),
    )

    trackId = models.ForeignKey(
        "tracks.Track",
        on_delete=models.CASCADE,
        related_name="playlist_tracks",
        db_column="track_id",
        verbose_name=_("track"),
    )

    position = models.PositiveSmallIntegerField(
        verbose_name=_("position"),
        db_column="position",
        validators=[MinValueValidator(1)],
    )

    selectionReason = models.CharField(
        max_length=16,
        verbose_name=_("selection reason"),
        db_column="selection_reason",
        choices=SelectionReason.choices,
        default=SelectionReason.MOOD_MATCH,
    )

    relevanceScore = models.FloatField(
        verbose_name=_("relevance score"),
        db_column="relevance_score",
        null=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    playState = models.CharField(
        max_length=16,
        verbose_name=_("play state"),
        db_column="play_state",
        choices=PlayState.choices,
        default=PlayState.QUEUED,
    )

    playedAt = models.DateTimeField(
        verbose_name=_("played at"),
        db_column="played_at",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "playlist_tracks"
        verbose_name = "Playlist Track"
        verbose_name_plural = "Playlist Tracks"
        managed = True

    def __str__(self):
        return f"{self.playlistId} - #{self.position} {self.trackId}"


class SavedPlaylist(HarmonicBaseModel):
    userId = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_playlists",
        db_column="user_id",
        verbose_name=_("user"),
    )

    playlistId = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name="saves",
        db_column="playlist_id",
        verbose_name=_("playlist"),
    )

    name = models.CharField(
        max_length=120,
        verbose_name=_("name"),
        db_column="name",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "saved_playlists"
        verbose_name = "Saved Playlist"
        verbose_name_plural = "Saved Playlists"
        managed = True

    def __str__(self):
        return f"{self.userId} saved -> {self.playlistId}"
