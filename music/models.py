from django.db import models
from harmonic_navigator.models import HarmonicBaseModel


class MusicTrack(HarmonicBaseModel):
    title = models.CharField(
        verbose_name="Title",
        max_length=255,
        null=True,
    )

    artist = models.CharField(
        verbose_name="Artist",
        max_length=255,
        null=True,
    )

    album = models.CharField(
        verbose_name="Album",
        max_length=255,
        null=True
    )

    duration = models.IntegerField(
        verbose_name="Duration",
        null=True,
    )

    class Meta:
        db_table = "music_tracks"
        verbose_name = "Music Track"
        verbose_name_plural = "Music Tracks"

    def __str__(self):
        return f"{self.title} by {self.artist}"
