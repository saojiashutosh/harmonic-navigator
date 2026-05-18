from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from harmonic_navigator.models import HarmonicBaseModel


class ConcertEvent(HarmonicBaseModel):
    """An upcoming live concert discovered for an artist in the catalog."""

    class SourceChoices(models.TextChoices):
        TICKETMASTER = "ticketmaster", "Ticketmaster"
        MANUAL = "manual", "Manual"

    artistId = models.ForeignKey(
        "tracks.Artist",
        on_delete=models.PROTECT,
        related_name="concert_events",
        db_column="artist_id",
        verbose_name=_("artist"),
    )
    externalId = models.CharField(
        max_length=128,
        verbose_name=_("externalId"),
        db_column="external_id",
        null=True,
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_("name"),
        db_column="name",
        null=True,
    )
    venueName = models.CharField(
        max_length=255,
        verbose_name=_("venueName"),
        db_column="venue_name",
        null=True,
        blank=True,
    )
    city = models.CharField(
        max_length=128,
        verbose_name=_("city"),
        db_column="city",
        null=True,
    )
    country = models.CharField(
        max_length=128,
        verbose_name=_("country"),
        db_column="country",
        null=True,
        blank=True,
    )
    eventDate = models.DateField(
        verbose_name=_("eventDate"),
        db_column="event_date",
        null=True,
        blank=True,
    )
    ticketUrl = models.CharField(
        max_length=500,
        verbose_name=_("ticketUrl"),
        db_column="ticket_url",
        null=True,
        blank=True,
    )
    imageUrl = models.CharField(
        max_length=500,
        verbose_name=_("imageUrl"),
        db_column="image_url",
        null=True,
        blank=True,
    )
    recentSetlist = models.JSONField(
        verbose_name=_("recentSetlist"),
        db_column="recent_setlist",
        default=list,
        blank=True,
    )
    source = models.CharField(
        max_length=20,
        verbose_name=_("source"),
        db_column="source",
        choices=SourceChoices.choices,
        default=SourceChoices.TICKETMASTER,
    )
    isActive = models.BooleanField(
        verbose_name=_("isActive"),
        db_column="is_active",
        default=True,
    )

    class Meta:
        db_table = "concert_events"
        verbose_name = "Concert Event"
        verbose_name_plural = "Concert Events"
        managed = True

    def __str__(self):
        return str(self.id)


class ConcertPlaylist(HarmonicBaseModel):
    """Links a generated 'get ready for the concert' playlist to its event."""

    concertEventId = models.ForeignKey(
        ConcertEvent,
        on_delete=models.CASCADE,
        related_name="concert_playlists",
        db_column="concert_event_id",
        verbose_name=_("concert event"),
    )
    playlistId = models.ForeignKey(
        "playlists.Playlist",
        on_delete=models.CASCADE,
        related_name="concert_playlist",
        db_column="playlist_id",
        verbose_name=_("playlist"),
    )
    userId = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="concert_playlists",
        db_column="user_id",
        verbose_name=_("user"),
        null=True,
        blank=True,
    )
    city = models.CharField(
        max_length=128,
        verbose_name=_("city"),
        db_column="city",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "concert_playlists"
        verbose_name = "Concert Playlist"
        verbose_name_plural = "Concert Playlists"
        managed = True

    def __str__(self):
        return str(self.id)
