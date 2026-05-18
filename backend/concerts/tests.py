from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework.test import APIClient

from helpers import allevents_client
from helpers.allevents_client import AllEventsScrapeError
from playlists.models import PlaylistTrack
from tracks.models import Artist, Track

from .models import ConcertEvent, ConcertPlaylist
from .services import build_concert_playlist, discover_concerts


class ConcertDiscoveryTests(TestCase):
    def setUp(self):
        self.artist = Artist.objects.create(name="Arijit Singh")

    @patch("concerts.services.allevents_client.search_events")
    def test_discover_matches_artist_named_in_event_title(self, mock_search):
        mock_search.return_value = [
            {
                "external_id": "EVT1",
                "name": "Arijit Singh Live in Concert",
                "venue_name": "DY Patil Stadium",
                "city": "Mumbai",
                "country": "India",
                "event_date": "2099-01-20",
                "ticket_url": "https://allevents.in/mumbai/arijit-singh-live",
                "image_url": "https://img.allevents.in/evt1.jpg",
                "attractions": [],
                "tags": ["bollywood", "live-music"],
            },
            {
                "external_id": "EVT2",
                "name": "Underground Techno Night",
                "city": "Mumbai",
                "event_date": "2099-02-01",
                "attractions": [],
                "tags": ["electronic"],
            },
        ]

        events = discover_concerts("Mumbai")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].artistId, self.artist)
        self.assertEqual(events[0].venueName, "DY Patil Stadium")
        self.assertEqual(events[0].source, ConcertEvent.SourceChoices.SCRAPED)
        self.assertEqual(ConcertEvent.objects.count(), 1)

    @patch("concerts.services.allevents_client.search_events")
    def test_discover_dedupes_same_concert_listed_twice(self, mock_search):
        mock_search.return_value = [
            {
                "external_id": "A1", "name": "Arijit Singh Live",
                "venue_name": "DY Patil Stadium", "city": "Mumbai",
                "event_date": "2099-01-20", "attractions": [], "tags": [],
            },
            {  # same artist + venue + date — a duplicate listing
                "external_id": "A2", "name": "Arijit Singh Live in Concert",
                "venue_name": "DY Patil Stadium", "city": "Mumbai",
                "event_date": "2099-01-20", "attractions": [], "tags": [],
            },
            {  # same artist + venue, different date — a separate show
                "external_id": "A3", "name": "Arijit Singh Live",
                "venue_name": "DY Patil Stadium", "city": "Mumbai",
                "event_date": "2099-03-15", "attractions": [], "tags": [],
            },
        ]

        discover_concerts("Mumbai")

        self.assertEqual(ConcertEvent.objects.count(), 2)

    @patch("concerts.services.allevents_client.search_events")
    def test_discover_skips_past_events(self, mock_search):
        mock_search.return_value = [
            {
                "external_id": "OLD",
                "name": "Arijit Singh Unplugged",
                "city": "Mumbai",
                "event_date": "2000-01-01",
                "attractions": [],
                "tags": [],
            }
        ]

        self.assertEqual(discover_concerts("Mumbai"), [])
        self.assertEqual(ConcertEvent.objects.count(), 0)

    @patch("concerts.services.allevents_client.search_events")
    def test_discover_endpoint_returns_manual_events_when_scrape_fails(self, mock_search):
        # Simulate the live scrape failing — manual concerts must still show.
        mock_search.side_effect = AllEventsScrapeError("site unreachable")
        ConcertEvent.objects.create(
            artistId=self.artist,
            name="Arijit Singh — Acoustic Evening",
            city="Mumbai",
            eventDate="2099-05-01",
            source=ConcertEvent.SourceChoices.MANUAL,
        )

        response = APIClient().post(
            "/concerts/events/discover/", {"city": "Mumbai"}, format="json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["events"][0]["source"], "manual")


class ConcertPlaylistTests(TestCase):
    def setUp(self):
        self.artist = Artist.objects.create(name="Arijit Singh")
        self.event = ConcertEvent.objects.create(
            artistId=self.artist,
            externalId="EVT1",
            name="Arijit Singh Live",
            city="Mumbai",
            eventDate="2099-01-20",
        )
        self.hit = Track.objects.create(title="Tum Hi Ho", artistId=self.artist)
        self.deep_cut = Track.objects.create(title="Phir Le Aaya Dil", artistId=self.artist)
        # JioSaavn top-up is stubbed off by default; tests opt in by setting
        # a return value — keeps the rest from making real network calls.
        saavn_patcher = patch(
            "concerts.services.saavn_client.search_songs", return_value=[],
        )
        self.mock_saavn = saavn_patcher.start()
        self.addCleanup(saavn_patcher.stop)

    @patch("concerts.services.setlistfm_client.recent_setlists")
    def test_setlist_songs_rank_above_other_artist_tracks(self, mock_setlist):
        mock_setlist.return_value = [{"song": "Tum Hi Ho", "count": 8}]

        concert_playlist = build_concert_playlist(self.event, limit=10)

        self.assertIsInstance(concert_playlist, ConcertPlaylist)
        tracks = list(
            PlaylistTrack.objects
            .filter(playlistId=concert_playlist.playlistId)
            .order_by("position")
        )
        self.assertEqual(tracks[0].trackId, self.hit)
        self.assertEqual(
            tracks[0].selectionReason, PlaylistTrack.SelectionReason.TAG_MATCH,
        )
        self.assertGreater(tracks[0].relevanceScore, tracks[1].relevanceScore)

    @patch("concerts.services.setlistfm_client.recent_setlists")
    def test_playlist_builds_without_setlist_data(self, mock_setlist):
        mock_setlist.return_value = []

        concert_playlist = build_concert_playlist(self.event, limit=10)

        self.assertEqual(concert_playlist.playlistId.trackCount, 2)

    @patch("concerts.services.setlistfm_client.recent_setlists")
    def test_playlist_deduplicates_title_variants(self, mock_setlist):
        mock_setlist.return_value = []
        # The same song re-imported under a "From ..." variant title.
        Track.objects.create(
            title='Tum Hi Ho - From "Aashiqui 2"', artistId=self.artist,
        )

        concert_playlist = build_concert_playlist(self.event, limit=25)

        # "Tum Hi Ho" + its variant collapse to one; "Phir Le Aaya Dil" stays.
        self.assertEqual(concert_playlist.playlistId.trackCount, 2)

    @patch("concerts.services.setlistfm_client.recent_setlists")
    def test_playlist_tops_up_from_jiosaavn_when_catalog_thin(self, mock_setlist):
        mock_setlist.return_value = []
        self.mock_saavn.return_value = [
            {
                "saavn_id": f"s{i}",
                "title": f"Online Song {i}",
                "artist": "Arijit Singh",
                "language": "hindi",
                "year": 2020,
                "duration_ms": 240000,
                "is_explicit": False,
                "image_url": None,
            }
            for i in range(4)
        ]

        concert_playlist = build_concert_playlist(self.event, limit=25)

        titles = set(
            PlaylistTrack.objects
            .filter(playlistId=concert_playlist.playlistId)
            .values_list("trackId__title", flat=True)
        )
        self.assertIn("Online Song 0", titles)
        # 2 local setUp tracks + 4 imported from JioSaavn.
        self.assertEqual(concert_playlist.playlistId.trackCount, 6)

    @patch("concerts.services.setlistfm_client.recent_setlists")
    def test_playlist_contains_only_the_concert_artist(self, mock_setlist):
        mock_setlist.return_value = []
        # A high-energy track by a different artist must NOT leak in as filler.
        other = Artist.objects.create(name="Some Other Band")
        Track.objects.create(
            title="Unrelated Anthem", artistId=other, primaryMood="energized",
        )

        concert_playlist = build_concert_playlist(self.event, limit=25)

        artist_ids = set(
            PlaylistTrack.objects
            .filter(playlistId=concert_playlist.playlistId)
            .values_list("trackId__artistId", flat=True)
        )
        self.assertEqual(artist_ids, {self.artist.id})


class ConcertScraperTests(TestCase):
    """Real-time scraper — schema.org JSON-LD parsing (AllEvents format)."""

    # AllEvents embeds a top-level JSON array of schema.org Event objects.
    JSONLD_PAGE = """
    <html><head>
    <script type="application/ld+json">
    [{"@context":"https://schema.org","@type":"Event",
      "name":"Lucky Ali Live in Concert",
      "startDate":"2099-07-11",
      "url":"https://allevents.in/mumbai/lucky-ali-live/39000",
      "image":"https://cdn.allevents.in/lucky-ali.jpg",
      "location":{"@type":"Place","name":"Shanmukhananda Hall",
                  "address":{"@type":"PostalAddress","addressLocality":"Mumbai"}}}]
    </script>
    </head><body></body></html>
    """

    def _scrape(self, html):
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status.return_value = None
        with patch("helpers.allevents_client.requests.get", return_value=mock_response), \
                patch("helpers.allevents_client.cache.get", return_value=None), \
                patch("helpers.allevents_client.cache.set"):
            return allevents_client.search_events("Mumbai")

    def test_search_events_parses_schema_org_jsonld(self):
        events = self._scrape(self.JSONLD_PAGE)

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["name"], "Lucky Ali Live in Concert")
        self.assertEqual(event["venue_name"], "Shanmukhananda Hall")
        self.assertEqual(event["event_date"], "2099-07-11")
        self.assertEqual(event["city"], "Mumbai")

    def test_search_events_raises_on_unreachable_site(self):
        import requests

        with patch(
            "helpers.allevents_client.requests.get",
            side_effect=requests.RequestException("connection refused"),
        ), patch("helpers.allevents_client.cache.get", return_value=None):
            with self.assertRaises(AllEventsScrapeError):
                allevents_client.search_events("Mumbai")
