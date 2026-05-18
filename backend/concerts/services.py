from __future__ import annotations

import re
from datetime import date

from django.db import transaction

from helpers import setlistfm_client, ticketmaster_client
from helpers.setlistfm_client import SetlistFmConfigurationError
from playlists.models import Playlist, PlaylistTrack
from tracks.models import Artist, Track

from .constants import (
    CONCERT_FILLER_MOODS,
    CONCERT_MOOD_LABEL,
    DEFAULT_CONCERT_PLAYLIST_SIZE,
    SETLIST_SONG_LIMIT,
)
from .models import ConcertEvent, ConcertPlaylist

# Strip parenthetical / dash-suffix variants so "Yellow (Live)" and
# "Yellow - Remastered" both normalise to the same base title.
_VARIANT_RE = re.compile(
    r"\s*[\(\[\{][^\)\]\}]*[\)\]\}]"
    r"|\s*[-–]\s*(remaster(?:ed)?|live|acoustic|radio\s+edit|version|edit).*$",
    re.IGNORECASE,
)


def _normalise_title(title: str | None) -> str:
    if not title:
        return ""
    cleaned = _VARIANT_RE.sub("", title)
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _normalise_artist(name: str | None) -> str:
    return re.sub(r"[^\w]", "", (name or "").lower())


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def discover_concerts(
    city: str,
    *,
    country_code: str | None = None,
) -> list[ConcertEvent]:
    """Discover upcoming concerts in `city` for artists in the catalog.

    Queries Ticketmaster once for the city, matches each event's attractions
    against the Artist catalog, and upserts a ConcertEvent per matched
    (artist, event) pair. Past-dated events are skipped.
    """
    events = ticketmaster_client.search_events(city, country_code=country_code)
    if not events:
        return []

    artist_index = {
        _normalise_artist(artist.name): artist
        for artist in Artist.objects.all()
        if artist.name
    }

    discovered: list[ConcertEvent] = []
    seen: set[tuple] = set()
    today = date.today()

    for event in events:
        event_date = _parse_date(event.get("event_date"))
        if event_date and event_date < today:
            continue
        for attraction in event.get("attractions") or []:
            artist = artist_index.get(_normalise_artist(attraction))
            if artist is None:
                continue
            key = (event.get("external_id"), artist.id)
            if key in seen:
                continue
            seen.add(key)

            concert, _ = ConcertEvent.objects.update_or_create(
                externalId=event.get("external_id"),
                artistId=artist,
                defaults={
                    "name": event.get("name"),
                    "venueName": event.get("venue_name"),
                    "city": event.get("city") or city,
                    "country": event.get("country"),
                    "eventDate": event_date,
                    "ticketUrl": event.get("ticket_url"),
                    "imageUrl": event.get("image_url"),
                    "source": ConcertEvent.SourceChoices.TICKETMASTER,
                    "isActive": True,
                },
            )
            discovered.append(concert)

    return discovered


def ensure_setlist(event: ConcertEvent, *, refresh: bool = False) -> list[dict]:
    """Return the artist's recent setlist, fetching it from setlist.fm once.

    Setlist weighting is optional: when no API key is configured the playlist
    still builds from the artist's catalog, so a missing key is swallowed here.
    """
    if event.recentSetlist and not refresh:
        return event.recentSetlist

    try:
        setlist = setlistfm_client.recent_setlists(
            event.artistId.name, song_limit=SETLIST_SONG_LIMIT,
        )
    except SetlistFmConfigurationError:
        return []

    event.recentSetlist = setlist
    event.save(update_fields=["recentSetlist", "updatedAt"])
    return setlist


def build_concert_playlist(
    event: ConcertEvent,
    *,
    limit: int = DEFAULT_CONCERT_PLAYLIST_SIZE,
    user=None,
) -> ConcertPlaylist:
    """Generate a "get ready for the concert" playlist for an event.

    Tracks are weighted toward the artist's recent setlist songs, then their
    remaining catalog, then high-energy filler tracks so the playlist still
    reaches `limit` when the artist's catalog is thin.
    """
    setlist = ensure_setlist(event)
    setlist_weights = {
        _normalise_title(item.get("song")): item.get("count", 1)
        for item in setlist
        if item.get("song")
    }
    max_count = max(setlist_weights.values(), default=1)

    artist_tracks = Track.objects.select_related("artistId").filter(
        artistId=event.artistId, isActive=True,
    )

    scored: list[tuple[Track, float, str]] = []
    seen_titles: set[str] = set()
    for track in artist_tracks:
        base = _normalise_title(track.title)
        if base and base in seen_titles:
            continue
        seen_titles.add(base)

        weight = setlist_weights.get(base)
        if weight is not None:
            # Setlist match — scaled by how often the song appears in recent
            # shows, so the artist's current live staples rank highest.
            score = 2.0 + (weight / max_count)
            reason = PlaylistTrack.SelectionReason.TAG_MATCH
        else:
            score = 1.0
            reason = PlaylistTrack.SelectionReason.MOOD_MATCH
        scored.append((track, score, reason))

    scored.sort(key=lambda item: item[1], reverse=True)

    # Fill remaining slots with high-energy tracks so the playlist hits `limit`
    # even for artists with a sparse catalog — live prep should feel full.
    if len(scored) < limit:
        existing_ids = {track.id for track, _, _ in scored}
        fillers = (
            Track.objects.select_related("artistId")
            .filter(isActive=True, primaryMood__in=CONCERT_FILLER_MOODS)
            .exclude(id__in=existing_ids)
            .order_by("-artistPopularity")[: limit - len(scored)]
        )
        for track in fillers:
            scored.append((track, 0.5, PlaylistTrack.SelectionReason.FALLBACK))

    chosen = scored[:limit]
    owner = user if (user is not None and user.is_authenticated) else None

    with transaction.atomic():
        playlist = Playlist.objects.create(
            userId=owner,
            moodLabel=CONCERT_MOOD_LABEL,
            status=(
                Playlist.StatusChoices.READY
                if chosen
                else Playlist.StatusChoices.FAILED
            ),
            trackCount=len(chosen),
        )
        PlaylistTrack.objects.bulk_create(
            [
                PlaylistTrack(
                    playlistId=playlist,
                    trackId=track,
                    position=index,
                    selectionReason=reason,
                    relevanceScore=round(min(score, 4.0), 4),
                )
                for index, (track, score, reason) in enumerate(chosen, start=1)
            ]
        )
        concert_playlist = ConcertPlaylist.objects.create(
            concertEventId=event,
            playlistId=playlist,
            userId=owner,
            city=event.city,
        )

    return concert_playlist
