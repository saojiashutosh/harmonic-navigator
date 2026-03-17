from django.utils.translation import gettext_lazy as _
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from harmonic_navigator.models import HarmonicBaseModel


class MoodTag(HarmonicBaseModel):
    name = models.CharField(
        max_length=64,
        verbose_name=_("name"),
        db_column="name",
        null=True,
    )
    mood = models.CharField(
        max_length=32,
        verbose_name=_("mood"),
        db_column="mood",
        null=True,
    )
    color = models.CharField(
        max_length=7,
        verbose_name=_("color"),
        db_column="color",
        default="#cccccc",
    )

    class Meta:
        db_table = "mood_tags"
        verbose_name = "Mood Tag"
        verbose_name_plural = "Mood Tags"
        managed = True

    def __str__(self):
        return str(self.id)


class Artist(HarmonicBaseModel):
    name = models.CharField(
        max_length=255,
        verbose_name=_("name"),
        db_column="name",
        null=True,
    )
    spotify_id = models.CharField(
        max_length=64,
        verbose_name=_("spotify_id"),
        db_column="spotify_id",
        null=True,
    )

    class Meta:
        db_table = "artists"
        verbose_name = "Artist"
        verbose_name_plural = "Artists"
        managed = True

    def __str__(self):
        return str(self.id)


class Track(HarmonicBaseModel):

    class TypeChoices(models.TextChoices):
        SONG = "song",         "Song"
        INSTRUMENTAL = "instrumental", "Instrumental"
        AMBIENT = "ambient",      "Ambient"

    class SourceChoices(models.TextChoices):
        SPOTIFY = "spotify", "Spotify"
        FMA = "fma",     "Free Music Archive"
        MANUAL = "manual",  "Manual"

    title = models.CharField(
        max_length=255,
        verbose_name=_("title"),
        db_column="title",
        null=True,
    )
    artist = models.ForeignKey(
        Artist,
        on_delete=models.PROTECT,
        related_name="tracks",
        db_column="artist_id",
        verbose_name=_("artist"),
    )
    type = models.CharField(
        max_length=20,
        verbose_name=_("type"),
        db_column="type",
        choices=TypeChoices.choices,
        default=TypeChoices.SONG,
    )
    source = models.CharField(
        max_length=20,
        verbose_name=_("source"),
        db_column="source",
        choices=SourceChoices.choices,
        default=SourceChoices.MANUAL,
    )
    spotify_id = models.CharField(
        max_length=64,
        verbose_name=_("spotify_id"),
        db_column="spotify_id",
        null=True,
    )
    fma_id = models.CharField(
        max_length=64,
        verbose_name=_("fma_id"),
        db_column="fma_id",
        null=True,
    )
    preview_url = models.CharField(
        max_length=255,
        verbose_name=_("preview_url"),
        db_column="preview_url",
        null=True,
    )
    external_url = models.CharField(
        max_length=255,
        verbose_name=_("external_url"),
        db_column="external_url",
        null=True,
    )
    tempo_bpm = models.PositiveSmallIntegerField(
        verbose_name=_("tempo_bpm"),
        db_column="tempo_bpm",
        null=True,
        validators=[MinValueValidator(40), MaxValueValidator(220)],
    )
    duration_ms = models.PositiveIntegerField(
        verbose_name=_("duration_ms"),
        db_column="duration_ms",
        null=True,
    )
    key_signature = models.CharField(
        max_length=16,
        verbose_name=_("key_signature"),
        db_column="key_signature",
        null=True,
    )
    energy = models.FloatField(
        verbose_name=_("energy"),
        db_column="energy",
        null=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    valence = models.FloatField(
        verbose_name=_("valence"),
        db_column="valence",
        null=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    acousticness = models.FloatField(
        verbose_name=_("acousticness"),
        db_column="acousticness",
        null=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    instrumentalness = models.FloatField(
        verbose_name=_("instrumentalness"),
        db_column="instrumentalness",
        null=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    loudness = models.FloatField(
        verbose_name=_("loudness"),
        db_column="loudness",
        null=True,
        validators=[MinValueValidator(-60.0), MaxValueValidator(0.0)],
    )
    primary_mood = models.CharField(
        max_length=32,
        verbose_name=_("primary_mood"),
        db_column="primary_mood",
        null=True,
    )
    is_instrumental = models.BooleanField(
        verbose_name=_("is_instrumental"),
        db_column="is_instrumental",
        default=False,
    )
    is_explicit = models.BooleanField(
        verbose_name=_("is_explicit"),
        db_column="is_explicit",
        default=False,
    )
    is_active = models.BooleanField(
        verbose_name=_("is_active"),
        db_column="is_active",
        default=True,
    )
    features_synced_at = models.DateTimeField(
        verbose_name=_("features_synced_at"),
        db_column="features_synced_at",
        null=True,
    )

    class Meta:
        db_table = "tracks"
        verbose_name = "Track"
        verbose_name_plural = "Tracks"
        managed = True

    def __str__(self):
        return str(self.id)

    @property
    def duration_minutes(self):
        if self.duration_ms:
            seconds = self.duration_ms // 1000
            return f"{seconds // 60}:{seconds % 60:02d}"
        return None


class TrackMoodTag(HarmonicBaseModel):

    class TagSource(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTO = "auto", "Auto"
        INFERRED = "inferred", "Inferred"

    track = models.ForeignKey(
        Track,
        on_delete=models.CASCADE,
        related_name="track_mood_tags",
        db_column="track_id",
        verbose_name=_("track"),
    )
    mood_tag = models.ForeignKey(
        MoodTag,
        on_delete=models.CASCADE,
        related_name="track_mood_tags",
        db_column="mood_tag_id",
        verbose_name=_("mood tag"),
    )
    weight = models.FloatField(
        verbose_name=_("weight"),
        db_column="weight",
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    tag_source = models.CharField(
        max_length=16,
        verbose_name=_("tag source"),
        db_column="tag_source",
        choices=TagSource.choices,
        default=TagSource.MANUAL,
    )

    class Meta:
        db_table = "track_mood_tags"
        verbose_name = "Track Mood Tag"
        verbose_name_plural = "Track Mood Tags"
        managed = True

    def __str__(self):
        return str(self.id)


class AudioFeatureSnapshot(HarmonicBaseModel):
    track = models.ForeignKey(
        Track,
        on_delete=models.CASCADE,
        related_name="audio_feature_snapshots",
        db_column="track_id",
        verbose_name=_("track"),
    )
    snapshot = models.JSONField(
        verbose_name=_("snapshot"),
        db_column="snapshot",
        default=dict,
    )
    synced_at = models.DateTimeField(
        verbose_name=_("synced at"),
        db_column="synced_at",
        auto_now_add=True,
    )

    class Meta:
        db_table = "audio_feature_snapshots"
        verbose_name = "Audio Feature Snapshot"
        verbose_name_plural = "Audio Feature Snapshots"
        managed = True

    def __str__(self):
        return str(self.id)
