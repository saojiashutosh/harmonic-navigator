from unittest.mock import patch

from django.test import TestCase

from playlists.models import PlaylistTrack
from tracks.models import Artist, Track

from .models import ConcertEvent, ConcertPlaylist
from .services import build_concert_playlist, discover_concerts


class ConcertDiscoveryTests(TestCase):
    def setUp(self):
        self.artist = Artist.objects.create(name="Coldplay")

    @patch("concerts.services.ticketmaster_client.search_events")
    def test_discover_matches_only_catalog_artists(self, mock_search):
        mock_search.return_value = [
            {
                "external_id": "EVT1",
                "name": "Coldplay: Music of the Spheres",
                "venue_name": "DY Patil Stadium",
                "city": "Mumbai",
                "country": "India",
                "event_date": "2099-01-20",
                "ticket_url": "https://tickets.example/evt1",
                "image_url": "https://img.example/evt1.jpg",
                "attractions": ["Coldplay"],
            },
            {
                "external_id": "EVT2",
                "name": "Unknown Band Live",
                "event_date": "2099-02-01",
                "city": "Mumbai",
                "attractions": ["Nobody In Catalog"],
            },
        ]

        events = discover_concerts("Mumbai")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].artistId, self.artist)
        self.assertEqual(events[0].venueName, "DY Patil Stadium")
        self.assertEqual(ConcertEvent.objects.count(), 1)

    @patch("concerts.services.ticketmaster_client.search_events")
    def test_discover_skips_past_events(self, mock_search):
        mock_search.return_value = [
            {
                "external_id": "OLD",
                "name": "An old show",
                "city": "Mumbai",
                "event_date": "2000-01-01",
                "attractions": ["Coldplay"],
            }
        ]

        self.assertEqual(discover_concerts("Mumbai"), [])
        self.assertEqual(ConcertEvent.objects.count(), 0)


class ConcertPlaylistTests(TestCase):
    def setUp(self):
        self.artist = Artist.objects.create(name="Coldplay")
        self.event = ConcertEvent.objects.create(
            artistId=self.artist,
            externalId="EVT1",
            name="Coldplay Live",
            city="Mumbai",
            eventDate="2099-01-20",
        )
        self.hit = Track.objects.create(title="Yellow", artistId=self.artist)
        self.deep_cut = Track.objects.create(title="Sparks", artistId=self.artist)

    @patch("concerts.services.setlistfm_client.recent_setlists")
    def test_setlist_songs_rank_above_other_artist_tracks(self, mock_setlist):
        mock_setlist.return_value = [{"song": "Yellow", "count": 8}]

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
