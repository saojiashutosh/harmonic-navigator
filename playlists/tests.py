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
                Answer(moodSessionId=session, questionId=question_map["music_preference"], rawValue="no_lyrics", value=1.0),
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
        self.assertEqual(playlist.trackCount, 2)

        playlist_tracks = list(
            PlaylistTrack.objects.filter(playlistId=playlist).order_by("position")
        )
        self.assertEqual(playlist_tracks[0].trackId.title, "Deep Focus")
        self.assertGreaterEqual(playlist_tracks[0].relevanceScore, playlist_tracks[1].relevanceScore)
        playlist_track_response = self.client.get("/playlists/playlist-tracks/")
        self.assertEqual(playlist_track_response.status_code, status.HTTP_200_OK)
        self.assertEqual(playlist_track_response.data[0]["track"]["title"], "Deep Focus")
