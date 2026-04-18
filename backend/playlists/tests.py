from rest_framework import status
from rest_framework.test import APITestCase

from moods.constants import QUESTION_DEFINITIONS
from moods.models import Answer, MoodInference, MoodSession, Question
from playlists.models import Playlist, PlaylistTrack
from tracks.models import Artist, Track
from users.models import Users


class PlaylistGenerationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = Users.objects.create_user(
            email="playlist@example.com",
            password="secret123",
            firstName="Playlist",
            lastName="Tester",
            level=1,
            phoneNumber="1234567890",
        )
        Question.objects.bulk_create(
            [
                Question(
                    key=definition["key"],
                    text=definition["text"],
                    category=definition["category"],
                    inputType=definition["inputType"],
                    options=definition["options"],
                    order=definition["order"],
                    isActive=True,
                )
                for definition in QUESTION_DEFINITIONS
            ]
        )
        artist = Artist.objects.create(name="Artist One", spotifyId="artist-1")
        preferred_artist = Artist.objects.create(name="Teju Beats", spotifyId="artist-2")
        Track.objects.create(
            title="Deep Focus",
            artistId=artist,
            type=Track.TypeChoices.INSTRUMENTAL,
            source=Track.SourceChoices.MANUAL,
            energy=0.55,
            valence=0.45,
            primaryMood="focused",
            isInstrumental=True,
            isExplicit=False,
            isActive=True,
        )
        Track.objects.create(
            title="Hindi Focus Flow",
            artistId=artist,
            type=Track.TypeChoices.SONG,
            source=Track.SourceChoices.MANUAL,
            energy=0.55,
            valence=0.45,
            primaryMood="focused",
            language="hindi",
            genre="bollywood",
            region="india",
            artistPopularity=80,
            isInstrumental=False,
            isExplicit=False,
            isActive=True,
        )
        Track.objects.create(
            title="Party Starter",
            artistId=artist,
            type=Track.TypeChoices.SONG,
            source=Track.SourceChoices.MANUAL,
            energy=0.95,
            valence=0.95,
            primaryMood="celebratory",
            isInstrumental=False,
            isExplicit=False,
            isActive=True,
        )
        Track.objects.create(
            title="Teju Hindi Focus",
            artistId=preferred_artist,
            type=Track.TypeChoices.SONG,
            source=Track.SourceChoices.MANUAL,
            energy=0.52,
            valence=0.44,
            primaryMood="focused",
            language="hindi",
            genre="bollywood",
            region="india",
            artistPopularity=95,
            isInstrumental=False,
            isExplicit=False,
            isActive=True,
        )

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    def test_generate_playlist_creates_ranked_tracks(self):
        session = MoodSession.objects.create(userId=self.user)
        question_map = {question.key: question for question in Question.objects.all()}
        Answer.objects.bulk_create(
            [
                Answer(moodSessionId=session, questionId=question_map["energy_level"], rawValue="good", value=1.0),
                Answer(moodSessionId=session, questionId=question_map["emotional_tone"], rawValue="happy", value=1.0),
                Answer(moodSessionId=session, questionId=question_map["mental_state"], rawValue="sharp", value=1.0),
                Answer(moodSessionId=session, questionId=question_map["activity"], rawValue="working", value=1.0),
                Answer(moodSessionId=session, questionId=question_map["social_setting"], rawValue="meeting", value=1.0),
                Answer(moodSessionId=session, questionId=question_map["music_preference"], rawValue="lyrics", value=1.0),
                Answer(moodSessionId=session, questionId=question_map["music_language"], rawValue="hindi", value=1.0),
                Answer(moodSessionId=session, questionId=question_map["music_style"], rawValue="bollywood", value=1.0),
                Answer(moodSessionId=session, questionId=question_map["playlist_goal"], rawValue="focus", value=1.0),
                Answer(moodSessionId=session, questionId=question_map["preferred_artist"], rawValue="Teju", value=1.0),
            ]
        )
        MoodInference.objects.create(
            moodSessionId=session,
            moodLabel="focused",
            confidence=0.88,
            rawScores={"focused": 0.88},
        )

        response = self.client.post(
            "/playlists/playlists/generate/",
            {"moodSessionId": str(session.id), "limit": 5},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        playlist = Playlist.objects.get(id=response.data["id"])
        self.assertEqual(playlist.moodLabel, "focused")
        self.assertEqual(playlist.trackCount, 4)

        playlist_tracks = list(
            PlaylistTrack.objects.filter(playlistId=playlist).order_by("position")
        )
        self.assertEqual(playlist_tracks[0].trackId.title, "Teju Hindi Focus")
        self.assertGreaterEqual(playlist_tracks[0].relevanceScore, playlist_tracks[1].relevanceScore)
        playlist_track_response = self.client.get(f"/playlists/playlist-tracks/?playlistId={playlist.id}")
        self.assertEqual(playlist_track_response.status_code, status.HTTP_200_OK)
        playlist_track_payload = (
            playlist_track_response.data
            if isinstance(playlist_track_response.data, list)
            else playlist_track_response.data["results"]
        )
        payload_titles = [row["track"]["title"] for row in playlist_track_payload]
        payload_languages = {row["track"]["title"]: row["track"]["language"] for row in playlist_track_payload}
        self.assertIn("Teju Hindi Focus", payload_titles)
        self.assertEqual(payload_languages["Teju Hindi Focus"], "hindi")

    def test_generate_playlist_allows_guest_sessions(self):
        self.client.force_authenticate(user=None)
        session = MoodSession.objects.create(userId=None)
        question_map = {question.key: question for question in Question.objects.all()}
        Answer.objects.bulk_create(
            [
                Answer(moodSessionId=session, questionId=question_map["energy_level"], rawValue="low", value=0.6),
                Answer(moodSessionId=session, questionId=question_map["emotional_tone"], rawValue="calm", value=1.0),
                Answer(moodSessionId=session, questionId=question_map["mental_state"], rawValue="drifting", value=0.8),
                Answer(moodSessionId=session, questionId=question_map["activity"], rawValue="relaxing", value=1.0),
                Answer(moodSessionId=session, questionId=question_map["social_setting"], rawValue="alone", value=1.0),
                Answer(moodSessionId=session, questionId=question_map["music_preference"], rawValue="no_lyrics", value=1.0),
            ]
        )
        MoodInference.objects.create(
            moodSessionId=session,
            moodLabel="calm",
            confidence=0.72,
            rawScores={"calm": 0.72},
        )

        response = self.client.post(
            "/playlists/playlists/generate/",
            {"moodSessionId": str(session.id), "limit": 3},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        playlist = Playlist.objects.get(id=response.data["id"])
        self.assertIsNone(playlist.userId)
        self.assertEqual(playlist.moodLabel, "calm")
        self.assertLessEqual(playlist.trackCount, 3)
