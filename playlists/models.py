from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from harmonic_navigator.models import HarmonicBaseModel


class Playlist(HarmonicBaseModel):
    class StatusChoices(models.TextChoices):
        PENDING = "pending",   "Pending"
        READY = "ready",     "Ready"
        FAILED = "failed",    "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="playlists",
        db_column="user_id",
        verbose_name=_("user"),
    )

    mood_inference = models.ForeignKey(
        "moods.MoodInference",
        on_delete=models.SET_NULL,
        null=True,
        related_name="playlists",
        db_column="mood_inference_id",
        verbose_name=_("mood inference"),
    )

    mood_label = models.CharField(
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

    is_saved = models.BooleanField(
        verbose_name=_("is saved"),
        db_column="is_saved",
        default=False,
    )
    saved_at = models.DateTimeField(
        verbose_name=_("saved at"),
        db_column="saved_at",
        null=True,
        blank=True,
    )

    track_count = models.PositiveSmallIntegerField(
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
        return f"{self.mood_label} playlist — {self.user} ({self.status})"


class PlaylistTrack(HarmonicBaseModel):

    class SelectionReason(models.TextChoices):
        MOOD_MATCH = "mood_match",  "Mood Match"
        TAG_MATCH = "tag_match",   "Tag Match"
        NOVELTY = "novelty",     "Novelty"
        FALLBACK = "fallback",    "Fallback"

    class PlayState(models.TextChoices):
        QUEUED = "queued",    "Queued"
        PLAYED = "played",   "Played"
        SKIPPED = "skipped",  "Skipped"

    playlist = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name="playlist_tracks",
        db_column="playlist_id",
        verbose_name=_("playlist"),
    )

    track = models.ForeignKey(
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

    selection_reason = models.CharField(
        max_length=16,
        verbose_name=_("selection reason"),
        db_column="selection_reason",
        choices=SelectionReason.choices,
        default=SelectionReason.MOOD_MATCH,
    )

    relevance_score = models.FloatField(
        verbose_name=_("relevance score"),
        db_column="relevance_score",
        null=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    play_state = models.CharField(
        max_length=16,
        verbose_name=_("play state"),
        db_column="play_state",
        choices=PlayState.choices,
        default=PlayState.QUEUED,
    )

    played_at = models.DateTimeField(
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
        return f"{self.playlist} — #{self.position} {self.track}"


class SavedPlaylist(HarmonicBaseModel):

    user = models.ForeignKey(
        on_delete=models.CASCADE,
        related_name="saved_playlists",
        db_column="user_id",
        verbose_name=_("user"),
    )

    playlist = models.ForeignKey(
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
        return f"{self.user} saved → {self.playlist}"
