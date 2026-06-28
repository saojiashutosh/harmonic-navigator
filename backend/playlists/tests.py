from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from moods.constants import QUESTION_DEFINITIONS
from moods.models import Answer, MoodInference, MoodSession, Question
from playlists.constants import GUEST_PLAYLIST_SIZE, MOOD_TYPE_RATIOS
from playlists.models import Playlist, PlaylistTrack
from playlists.services import _score_track, _track_matches_era
from tracks.models import Artist, Track
from users.models import Users


def _score(track, mood_label, **overrides):
    """Thin wrapper around _score_track with sensible defaults for unit tests."""
    kwargs = dict(
        track=track,
        mood_label=mood_label,
        secondary_mood=None,
        mood_blend_ratio=1.0,
        type_weights=MOOD_TYPE_RATIOS.get(mood_label, {}),
        music_language=None,
        playlist_goal=None,
        preferred_artist=None,
        era_preference=None,
        time_of_day=None,
        feedback_map={},
        mood_tag_ids={},
    )
    kwargs.update(overrides)
    return _score_track(**kwargs)


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
                Answer(moodSessionId=session, questionId=question_map["music_language"], rawValue="hindi", value=1.0),
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
        # music_language=hindi applies a hard language filter, so only the two
        # hindi tracks in the fixture survive (Deep Focus / Party Starter are
        # dropped). The request-body "limit" is ignored — the view sizes the
        # playlist by auth tier (REGISTERED_PLAYLIST_SIZE).
        self.assertEqual(playlist.trackCount, 2)

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
        # The view sizes guest playlists by GUEST_PLAYLIST_SIZE (15), not the
        # request-body "limit". With no language/era filter and no calm-mood
        # tracks to trigger the mood filter, all four fixture tracks qualify.
        self.assertEqual(playlist.trackCount, 4)
        self.assertLessEqual(playlist.trackCount, GUEST_PLAYLIST_SIZE)


class MoodScoringUnitTests(TestCase):
    """Unit tests for the _score_track feature-confidence gating (Fix 2)."""

    @classmethod
    def setUpTestData(cls):
        cls.artist = Artist.objects.create(name="Scoring Artist", spotifyId="score-1")

    def _track(self, **kw):
        defaults = dict(
            title="T", artistId=self.artist, type=Track.TypeChoices.SONG,
            source=Track.SourceChoices.MANUAL, isActive=True,
        )
        defaults.update(kw)
        return Track.objects.create(**defaults)

    def test_null_feature_label_scores_below_feature_backed_match(self):
        """A bulk-defaulted 'energized' track with NO measured audio must rank
        below a genuinely-measured 'energized' track (the 1032-track problem)."""
        null_track = self._track(title="Bulk Energized", primaryMood="energized",
                                  energy=None, valence=None)
        real_track = self._track(title="Real Energized", primaryMood="energized",
                                 energy=0.85, valence=0.75)
        self.assertGreater(_score(real_track, "energized"), _score(null_track, "energized"))

    def test_contradicting_energy_discounts_the_mood_bonus(self):
        """A 'calm'-labelled track measured at high energy (0.7) must rank below
        one whose measured energy actually matches calm (0.2)."""
        true_calm = self._track(title="Truly Calm", primaryMood="calm",
                                 energy=0.20, valence=0.50)
        loud_calm = self._track(title="Loud 'Calm'", primaryMood="calm",
                                energy=0.70, valence=0.50)
        self.assertGreater(_score(true_calm, "calm"), _score(loud_calm, "calm"))

    def test_unknown_era_track_is_kept_not_dropped(self):
        """Fix 5: a track with no releaseYear (and no artist-era mapping) is
        treated as 'unknown' (kept) for an era request, not 'wrong' (dropped)."""
        unknown = self._track(title="Fresh Track", releaseYear=None)
        old = self._track(title="Old Track", releaseYear=1995)
        self.assertTrue(_track_matches_era(unknown, "latest"))
        self.assertFalse(_track_matches_era(old, "latest"))


class RecommendationBehaviourTests(APITestCase):
    """End-to-end generate() behaviour for the goal-blend, grounding and
    graceful-filter fixes."""

    @classmethod
    def setUpTestData(cls):
        cls.user = Users.objects.create_user(
            email="rec@example.com", password="secret123", firstName="Rec",
            lastName="Tester", level=1, phoneNumber="222",
        )
        Question.objects.bulk_create([
            Question(key=d["key"], text=d["text"], category=d["category"],
                     inputType=d["inputType"], options=d["options"], order=d["order"],
                     isActive=True)
            for d in QUESTION_DEFINITIONS
        ])
        cls.artist = Artist.objects.create(name="Rec Artist", spotifyId="rec-1")
        # A spread across moods, all feature-backed.
        specs = [
            ("Calm One", "calm", 0.20, 0.55), ("Calm Two", "calm", 0.25, 0.50),
            ("Calm Three", "calm", 0.22, 0.60), ("Focus One", "focused", 0.52, 0.45),
            ("Focus Two", "focused", 0.55, 0.42), ("Cele One", "celebratory", 0.90, 0.90),
            ("Cele Two", "celebratory", 0.88, 0.85),
        ]
        for title, mood, e, v in specs:
            Track.objects.create(
                title=title, artistId=cls.artist, type=Track.TypeChoices.SONG,
                source=Track.SourceChoices.MANUAL, primaryMood=mood, energy=e,
                valence=v, isActive=True,
            )

    def setUp(self):
        cache.clear()  # candidate pool is cached; isolate each test
        self.client.force_authenticate(user=self.user)

    def _session(self, mood_label, answers, confidence=0.9, secondary=None):
        session = MoodSession.objects.create(userId=self.user)
        qmap = {q.key: q for q in Question.objects.all()}
        Answer.objects.bulk_create([
            Answer(moodSessionId=session, questionId=qmap[k], rawValue=v, value=1.0)
            for k, v in answers.items()
        ])
        MoodInference.objects.create(
            moodSessionId=session, moodLabel=mood_label, confidence=confidence,
            rawScores={mood_label: confidence}, secondaryMoodLabel=secondary,
            moodBlendRatio=1.0,
        )
        return session

    def _generate(self, session):
        resp = self.client.post("/playlists/playlists/generate/",
                                {"moodSessionId": str(session.id)}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        playlist = Playlist.objects.get(id=resp.data["id"])
        rows = PlaylistTrack.objects.filter(playlistId=playlist).order_by("position")
        return playlist, [r.trackId for r in rows]

    def test_goal_relax_blends_in_confident_felt_mood(self):
        """Fix 1: a confident 'celebratory' reading + goal=relax must NOT return
        a 100%-calm playlist — some celebratory (felt-mood) tracks survive."""
        session = self._session("celebratory", {"emotional_tone": "excited",
                                                 "playlist_goal": "relax"})
        _, tracks = self._generate(session)
        moods = {t.primaryMood for t in tracks}
        self.assertIn("calm", moods)         # goal still leads
        self.assertIn("celebratory", moods)  # felt mood preserved (was 0% before)

    def test_anxious_serves_grounding_pool_not_empty(self):
        """Fix 6: an 'anxious' reading (no anxious catalogue) yields a non-empty
        grounding playlist of calm/focused tracks rather than nothing."""
        session = self._session("anxious", {"emotional_tone": "tense",
                                            "mental_state": "scattered"})
        _, tracks = self._generate(session)
        self.assertGreater(len(tracks), 0)
        self.assertTrue(all(t.primaryMood in {"calm", "focused"} for t in tracks))

    def test_mood_matches_lead_offmood_only_backfills(self):
        """Fix 3: trusted mood matches always lead; off-mood tracks only backfill
        to reach the limit instead of the old all-or-nothing contamination."""
        session = self._session("calm", {"emotional_tone": "calm"})
        _, tracks = self._generate(session)
        calm_positions = [i for i, t in enumerate(tracks) if t.primaryMood == "calm"]
        off_positions = [i for i, t in enumerate(tracks) if t.primaryMood != "calm"]
        self.assertTrue(calm_positions, "expected calm tracks to be present")
        if off_positions:
            self.assertLess(max(calm_positions), min(off_positions),
                            "every calm match must precede any off-mood backfill")
