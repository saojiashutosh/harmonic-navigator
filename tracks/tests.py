from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from tracks.models import Track
from tracks.services import (
    derive_is_instrumental,
    derive_primary_mood,
    derive_track_type,
    import_spotify_track,
)
from users.models import Users


class TrackServicesTests(APITestCase):
    def test_derives_track_metadata_from_audio_features(self):
        self.assertEqual(
            derive_track_type({"instrumentalness": 0.82, "energy": 0.4, "acousticness": 0.2}),
            Track.TypeChoices.INSTRUMENTAL,
        )
        self.assertEqual(
            derive_track_type({"instrumentalness": 0.1, "energy": 0.2, "acousticness": 0.7}),
            Track.TypeChoices.AMBIENT,
        )
        self.assertTrue(derive_is_instrumental({"instrumentalness": 0.7}))
        self.assertEqual(derive_primary_mood({"energy": 0.82, "valence": 0.83}), "celebratory")
        self.assertEqual(derive_primary_mood({"energy": 0.2, "valence": 0.7}), "calm")

    def test_import_spotify_track_persists_urls_and_features(self):
        track = import_spotify_track(
            {
                "spotify_id": "track-123",
                "title": "Focus Beam",
                "artist": {"spotify_id": "artist-123", "name": "Signal Path"},
                "preview_url": "https://p.scdn.co/mp3-preview/demo",
                "external_url": "https://open.spotify.com/track/track-123",
                "duration_ms": 180000,
                "is_explicit": False,
                "audio_features": {
                    "tempo": 118.2,
                    "key": 0,
                    "mode": 1,
                    "energy": 0.58,
                    "valence": 0.46,
                    "acousticness": 0.31,
                    "instrumentalness": 0.76,
                    "loudness": -11.4,
                },
            }
        )

        self.assertEqual(track.title, "Focus Beam")
        self.assertEqual(track.externalUrl, "https://open.spotify.com/track/track-123")
        self.assertEqual(track.previewUrl, "https://p.scdn.co/mp3-preview/demo")
        self.assertEqual(track.type, Track.TypeChoices.INSTRUMENTAL)
        self.assertEqual(track.primaryMood, "focused")
        self.assertEqual(track.keySignature, "C major")


class TrackImportApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = Users.objects.create_user(
            email="tracks@example.com",
            password="secret123",
            firstName="Track",
            lastName="Tester",
            level=1,
            phoneNumber="1234567890",
        )

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    @patch("tracks.views.import_spotify_search_results")
    def test_import_spotify_endpoint_returns_imported_tracks(self, mock_import):
        track = import_spotify_track(
            {
                "spotify_id": "track-999",
                "title": "Night Drive",
                "artist": {"spotify_id": "artist-999", "name": "City Echo"},
                "preview_url": "https://p.scdn.co/mp3-preview/night-drive",
                "external_url": "https://open.spotify.com/track/track-999",
                "duration_ms": 210000,
                "is_explicit": False,
                "audio_features": {"energy": 0.78, "valence": 0.52, "instrumentalness": 0.1, "acousticness": 0.15},
            }
        )
        mock_import.return_value = [track]

        response = self.client.post(
            "/tracks/tracks/import-spotify/",
            {"query": "night drive", "limit": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["tracks"][0]["title"], "Night Drive")
        self.assertEqual(
            response.data["tracks"][0]["externalUrl"],
            "https://open.spotify.com/track/track-999",
        )
