from __future__ import annotations

import re
from datetime import date

from django.db import transaction
from django.db.models import Q

from concerts.enrichment import estimate_audio_features
from helpers import allevents_client, saavn_client, setlistfm_client
from helpers.saavn_client import SaavnRequestError
from helpers.setlistfm_client import SetlistFmConfigurationError
from playlists.models import Playlist, PlaylistTrack
from tracks.models import Artist, Track

from .constants import (
    CONCERT_LANGUAGES,
    CONCERT_MOOD_LABEL,
    DEFAULT_CONCERT_PLAYLIST_SIZE,
    DEVOTIONAL_KEYWORDS,
    MIN_ARTIST_MATCH_LENGTH,
    ONLINE_FETCH_LIMIT,
    SETLIST_SONG_LIMIT,
)
from .models import ConcertEvent, ConcertPlaylist

# Collapse song-title variants so the same song imported under slightly
# different names dedupes to one playlist entry — parenthetical tags
# ("(Lofi)"), dash tails ('Song - From "Movie"', "- Reprise", remasters)
# and feat./from credits all reduce to the same base title.
_PAREN_RE = re.compile(r"[\(\[\{][^\)\]\}]*[\)\]\}]")
_DASH_TAIL_RE = re.compile(r"\s[-–|]\s.*$")
_CREDIT_TAIL_RE = re.compile(r"\b(from|feat|ft|featuring)\b.*$", re.IGNORECASE)


def _normalise_title(title: str | None) -> str:
    if not title:
        return ""
    text = _PAREN_RE.sub(" ", title)
    text = _DASH_TAIL_RE.sub("", text)
    text = _CREDIT_TAIL_RE.sub(" ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _normalise_phrase(value: str | None) -> str:
    """Lowercase, drop punctuation, collapse whitespace — for phrase matching."""
    cleaned = re.sub(r"[^\w\s]", " ", (value or "").lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _event_haystack(event: dict) -> str:
    """Searchable text for an event: its name plus any tags / attractions."""
    parts = [event.get("name") or ""]
    parts += event.get("attractions") or []
    parts += event.get("tags") or []
    return _normalise_phrase(" ".join(parts))


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _concert_identity(event: ConcertEvent) -> tuple:
    """Identity of a concert: same artist + venue + date is the same show.

    A different date is a genuinely different show. A null date can't be
    compared, so those events are given a unique key and never merged.
    """
    if event.eventDate is None:
        return ("__unique__", event.id)
    return (
        event.artistId_id,
        event.eventDate,
        (event.venueName or "").strip().lower(),
    )


def dedupe_concerts(events) -> list[ConcertEvent]:
    """Drop duplicate concert listings (same artist, venue and date)."""
    seen: set = set()
    unique: list[ConcertEvent] = []
    for event in events:
        identity = _concert_identity(event)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(event)
    return unique


def discover_concerts(city: str) -> list[ConcertEvent]:
    """Discover upcoming concerts in `city` for artists in the catalog.

    Scrapes AllEvents once for the city, then matches each event's name,
    tags and performers against catalog artist names (word-boundary match).
    A ConcertEvent is upserted per matched (artist, event) pair; past-dated
    events are skipped. Listing pages rarely expose a performer field, so
    matching leans on the event title — which for music gigs reliably leads
    with the headline act ("Hariharan in Mumbai", "Lucky Ali Live").
    """
    events = allevents_client.search_events(city)
    if not events:
        return []

    # Skip very short artist names — they cause false-positive substring hits.
    artist_patterns: list[tuple[Artist, re.Pattern]] = []
    for artist in Artist.objects.all():
        phrase = _normalise_phrase(artist.name)
        if len(phrase) >= MIN_ARTIST_MATCH_LENGTH:
            artist_patterns.append(
                (artist, re.compile(rf"\b{re.escape(phrase)}\b"))
            )

    discovered: list[ConcertEvent] = []
    seen: set[tuple] = set()
    today = date.today()

    for event in events:
        event_date = _parse_date(event.get("event_date"))
        if event_date and event_date < today:
            continue
        haystack = _event_haystack(event)
        if not haystack:
            continue
        for artist, pattern in artist_patterns:
            if not pattern.search(haystack):
                continue
            key = (event.get("external_id"), artist.id)
            if key in seen:
                continue
            seen.add(key)

            # Skip a listing that duplicates a concert already stored — same
            # artist + venue + date is the same show, even when AllEvents
            # lists it twice under different URLs. A different date is a
            # genuinely different show and is kept.
            if event_date and ConcertEvent.objects.filter(
                artistId=artist,
                eventDate=event_date,
                venueName=event.get("venue_name"),
            ).exclude(externalId=event.get("external_id")).exists():
                continue

            concert, _ = ConcertEvent.objects.update_or_create(
                externalId=event.get("external_id"),
                artistId=artist,
                defaults={
                    "name": event.get("name"),
                    "venueName": event.get("venue_name"),
                    "city": event.get("city") or city,
                    "country": event.get("country") or "India",
                    "eventDate": event_date,
                    "ticketUrl": event.get("ticket_url"),
                    "imageUrl": event.get("image_url"),
                    "source": ConcertEvent.SourceChoices.SCRAPED,
                    "isActive": True,
                },
            )
            discovered.append(concert)

    return discovered


def _is_devotional(*texts: str | None) -> bool:
    """True when any devotional keyword appears in the supplied text fragments."""
    haystack = " ".join(text.lower() for text in texts if text)
    return any(keyword in haystack for keyword in DEVOTIONAL_KEYWORDS)


def _eligible_artist_tracks(artist: Artist):
    """Return an artist's concert-eligible tracks.

    Concert playlists recommend Bollywood (Hindi) and Marathi songs only:
    a track qualifies when its language is Hindi/Marathi or its genre names
    one of those (covers "bollywood"). Devotional / spiritual songs — matched
    by keyword in the title or genre — are excluded.
    """
    language_match = Q(language__in=CONCERT_LANGUAGES)
    for term in (*CONCERT_LANGUAGES, "bollywood"):
        language_match |= Q(genre__icontains=term)

    devotional = Q()
    for keyword in DEVOTIONAL_KEYWORDS:
        devotional |= Q(title__icontains=keyword) | Q(genre__icontains=keyword)

    return (
        Track.objects.select_related("artistId")
        .filter(artistId=artist, isActive=True)
        .filter(language_match)
        .exclude(devotional)
    )


def _ensure_artist_tracks(artist: Artist, *, minimum: int) -> None:
    """Top up an artist's catalog from JioSaavn when too few tracks exist locally.

    Concert playlists are artist-only, so a thin local catalog would yield a
    short playlist. When fewer than `minimum` concert-eligible tracks (Bollywood
    / Marathi, non-devotional) are stored for the artist, fetch more of their
    songs from JioSaavn and import them under the same catalog artist. Songs
    that aren't Hindi/Marathi, or that look devotional, are skipped. Silently
    no-ops when JioSaavn is unreachable, falling back to what is stored locally.
    """
    existing = _eligible_artist_tracks(artist).count()
    if existing >= minimum:
        return

    artist_name = (artist.name or "").strip()
    if not artist_name:
        return

    try:
        songs = saavn_client.search_songs(artist_name, limit=ONLINE_FETCH_LIMIT)
    except SaavnRequestError:
        return

    target = _normalise_phrase(artist_name)
    for song in songs:
        candidate = _normalise_phrase(song.get("artist"))
        # JioSaavn search is fuzzy — only import songs actually by this artist.
        if not candidate or (
            candidate != target
            and target not in candidate
            and candidate not in target
        ):
            continue
        # Bollywood (Hindi) and Marathi only — skip other languages.
        if (song.get("language") or "").lower() not in CONCERT_LANGUAGES:
            continue
        # Keep devotional / spiritual songs out of concert playlists.
        if _is_devotional(song.get("title")):
            continue
        _import_saavn_track(song, artist)


def _import_saavn_track(song: dict, artist: Artist) -> None:
    """Create a Track for a JioSaavn song under the given catalog artist.

    Deduped by (artist, title) so repeated top-ups don't pile up rows. The
    track is enriched with heuristic audio features (energy, valence, mood,
    genre, region) so it participates in survey-based recommendation
    playlists — not just concert-only playlists.
    """
    title = song.get("title")
    if not title:
        return
    if Track.objects.filter(artistId=artist, title__iexact=title).exists():
        return

    # Estimate audio features from JioSaavn metadata so the track is
    # recommendation-ready for the survey pipeline.
    estimated = estimate_audio_features(
        title=title,
        language=song.get("language"),
        duration_ms=song.get("duration_ms"),
        artist_name=artist.name,
    )

    Track.objects.create(
        title=title,
        artistId=artist,
        type=Track.TypeChoices.SONG,
        source=Track.SourceChoices.MANUAL,
        language=song.get("language"),
        releaseYear=song.get("year"),
        durationMs=song.get("duration_ms"),
        isExplicit=song.get("is_explicit", False),
        isActive=True,
        # Heuristic audio features for recommendation scoring
        energy=estimated.get("energy"),
        valence=estimated.get("valence"),
        acousticness=estimated.get("acousticness"),
        instrumentalness=estimated.get("instrumentalness"),
        loudness=estimated.get("loudness"),
        primaryMood=estimated.get("primaryMood"),
        genre=estimated.get("genre"),
        region=estimated.get("region"),
        tempoBpm=estimated.get("tempoBpm"),
    )


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

    The playlist is built strictly from the concert artist's own songs —
    recent-setlist songs first (weighted by how often they're played live),
    then the rest of their tracks. No cross-artist filler: a Lucky Ali
    concert playlist contains only Lucky Ali songs. Only Bollywood (Hindi)
    and Marathi songs are recommended, and devotional songs are excluded.
    When the local catalog is too thin to fill the set, more of the
    artist's songs are fetched from JioSaavn first.
    """
    setlist = ensure_setlist(event)
    setlist_weights = {
        _normalise_title(item.get("song")): item.get("count", 1)
        for item in setlist
        if item.get("song")
    }
    max_count = max(setlist_weights.values(), default=1)

    # When the local catalog is too thin to fill the set, fetch more of the
    # artist's songs from JioSaavn before scoring.
    _ensure_artist_tracks(event.artistId, minimum=limit)

    artist_tracks = _eligible_artist_tracks(event.artistId)

    scored: list[tuple[Track, str, float, str]] = []
    for track in artist_tracks:
        base = _normalise_title(track.title)
        weight = setlist_weights.get(base)
        if weight is not None:
            # Setlist match — scaled by how often the song appears in recent
            # shows, so the artist's current live staples rank highest.
            score = 2.0 + (weight / max_count)
            reason = PlaylistTrack.SelectionReason.TAG_MATCH
        else:
            score = 1.0
            reason = PlaylistTrack.SelectionReason.MOOD_MATCH
        scored.append((track, base, score, reason))

    # Highest-scored first, then drop duplicate songs — keeping the best-ranked
    # copy of each (so a setlist-matched variant beats a plain re-import).
    scored.sort(key=lambda item: item[2], reverse=True)
    chosen: list[tuple[Track, float, str]] = []
    seen_titles: set[str] = set()
    for track, base, score, reason in scored:
        if base in seen_titles:
            continue
        seen_titles.add(base)
        chosen.append((track, score, reason))
        if len(chosen) >= limit:
            break
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
