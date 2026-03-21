from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from harmonic_navigator.models import HarmonicBaseModel


class TrackFeedback(HarmonicBaseModel):
    class ActionChoices(models.TextChoices):
        LIKE = "like", "Like"
        SKIP = "skip", "Skip"
        COMPLETE = "complete", "Complete"
        DISLIKE = "dislike", "Dislike"

    userId = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="track_feedbacks",
        db_column="user_id",
        verbose_name=_("user"),
    )

    trackId = models.ForeignKey(
        "tracks.Track",
        on_delete=models.CASCADE,
        related_name="feedbacks",
        db_column="track_id",
        verbose_name=_("track"),
    )

    playlistId = models.ForeignKey(
        "playlists.Playlist",
        on_delete=models.SET_NULL,
        null=True,
        related_name="feedbacks",
        db_column="playlist_id",
        verbose_name=_("playlist"),
    )

    playlistTrackId = models.ForeignKey(
        "playlists.PlaylistTrack",
        on_delete=models.SET_NULL,
        null=True,
        related_name="feedbacks",
        db_column="playlist_track_id",
        verbose_name=_("playlist track"),
    )

    moodSessionId = models.ForeignKey(
        "moods.MoodSession",
        on_delete=models.SET_NULL,
        null=True,
        related_name="feedbacks",
        db_column="mood_session_id",
        verbose_name=_("mood session"),
    )

    action = models.CharField(
        max_length=16,
        verbose_name=_("action"),
        db_column="action",
        choices=ActionChoices.choices,
    )

    listenProgress = models.FloatField(
        verbose_name=_("listen progress"),
        db_column="listen_progress",
        null=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    moodLabel = models.CharField(
        max_length=32,
        verbose_name=_("mood label"),
        db_column="mood_label",
        null=True,
    )

    class Meta:
        db_table = "track_feedbacks"
        verbose_name = "Track Feedback"
        verbose_name_plural = "Track Feedbacks"
        managed = True

    def __str__(self):
        return str(self.id)


class UserMoodPreference(HarmonicBaseModel):
    userId = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mood_preferences",
        db_column="user_id",
        verbose_name=_("user"),
    )

    moodLabel = models.CharField(
        max_length=32,
        verbose_name=_("mood label"),
        db_column="mood_label",
    )

    songWeight = models.FloatField(
        verbose_name=_("song weight"),
        db_column="song_weight",
        default=0.60,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    instrumentalWeight = models.FloatField(
        verbose_name=_("instrumental weight"),
        db_column="instrumental_weight",
        default=0.30,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    ambientWeight = models.FloatField(
        verbose_name=_("ambient weight"),
        db_column="ambient_weight",
        default=0.10,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    noveltyScore = models.FloatField(
        verbose_name=_("novelty score"),
        db_column="novelty_score",
        default=0.20,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    sampleCount = models.PositiveIntegerField(
        verbose_name=_("sample count"),
        db_column="sample_count",
        default=0,
    )

    lastComputedAt = models.DateTimeField(
        verbose_name=_("last computed at"),
        db_column="last_computed_at",
        null=True,
    )

    class Meta:
        db_table = "user_mood_preferences"
        verbose_name = "User Mood Preference"
        verbose_name_plural = "User Mood Preferences"
        managed = True

    def __str__(self):
        return str(self.id)

    @property
    def is_reliable(self):
        return self.sampleCount >= 10


class TrackMoodScore(HarmonicBaseModel):
    userId = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="track_mood_scores",
        db_column="user_id",
        verbose_name=_("user"),
    )

    trackId = models.ForeignKey(
        "tracks.Track",
        on_delete=models.CASCADE,
        related_name="mood_scores",
        db_column="track_id",
        verbose_name=_("track"),
    )

    moodLabel = models.CharField(
        max_length=32,
        verbose_name=_("mood label"),
        db_column="mood_label",
    )

    score = models.FloatField(
        verbose_name=_("score"),
        db_column="score",
        default=0.50,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    likeCount = models.PositiveIntegerField(
        default=0,
        db_column="like_count",
        verbose_name=_("like count"),
    )

    dislikeCount = models.PositiveIntegerField(
        default=0,
        db_column="dislike_count",
        verbose_name=_("dislike count"),
    )

    skipCount = models.PositiveIntegerField(
        default=0,
        db_column="skip_count",
        verbose_name=_("skip count"),
    )

    completeCount = models.PositiveIntegerField(
        default=0,
        db_column="complete_count",
        verbose_name=_("complete count"),
    )

    lastUpdatedAt = models.DateTimeField(
        verbose_name=_("last updated at"),
        db_column="last_updated_at",
        null=True,
    )

    class Meta:
        db_table = "track_mood_scores"
        verbose_name = "Track Mood Score"
        verbose_name_plural = "Track Mood Scores"
        managed = True

    def __str__(self):
        return str(self.id)
