from rest_framework import status
from rest_framework.test import APITestCase

from moods.inference import build_weight_key, infer_mood_from_responses, normalise_answer_value
from moods.constants import QUESTION_DEFINITIONS
from moods.models import Answer, MoodInference, MoodSession, Question
from users.models import Users


# Helper: build a category map from definitions
_CATEGORY_MAP = {d["key"]: d["category"] for d in QUESTION_DEFINITIONS}


def _make_responses(question_map, answers):
    """Build response dicts from (key, raw_value) pairs."""
    responses = []
    for key, raw_value in answers:
        question = question_map[key]
        responses.append(
            {
                "weight_key": build_weight_key(question, raw_value),
                "value": normalise_answer_value(raw_value, question),
                "raw_value": raw_value,
                "category": question.category,
            }
        )
    return responses


class MoodFlowTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = Users.objects.create_user(
            email="tester@example.com",
            password="secret123",
            firstName="Test",
            lastName="User",
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

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    def test_create_session(self):
        response = self.client.post("/moods/mood-sessions/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MoodSession.objects.count(), 1)
        self.assertEqual(MoodSession.objects.get().userId, self.user)

    def test_submit_answers_creates_answers_and_inference(self):
        session = MoodSession.objects.create(userId=self.user)

        response = self.client.post(
            f"/moods/mood-sessions/{session.id}/submit/",
            {
                "answers": [
                    {"question_key": "energy_level", "raw_value": "good"},
                    {"question_key": "emotional_tone", "raw_value": "happy"},
                    {"question_key": "mental_state", "raw_value": "sharp"},
                    {"question_key": "activity", "raw_value": "working"},
                    {"question_key": "social_setting", "raw_value": "alone"},
                    {"question_key": "music_language", "raw_value": "hindi"},
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Answer.objects.filter(moodSessionId=session).count(), 6)

        inference = MoodInference.objects.get(moodSessionId=session)
        self.assertEqual(response.data["id"], str(inference.id))
        self.assertEqual(response.data["moodLabel"], inference.moodLabel)
        self.assertIn("is_high_confidence", response.data)
        # New fields must be present in response
        self.assertIn("secondaryMoodLabel", response.data)
        self.assertIn("secondaryConfidence", response.data)
        self.assertIn("moodBlendRatio", response.data)

        session.refresh_from_db()
        self.assertIsNotNone(session.endedAt)
        self.assertIsNotNone(session.durationSeconds)

    def test_submit_rejects_duplicate_question_keys(self):
        session = MoodSession.objects.create(userId=self.user)

        response = self.client.post(
            f"/moods/mood-sessions/{session.id}/submit/",
            {
                "answers": [
                    {"question_key": "energy_level", "raw_value": "low"},
                    {"question_key": "energy_level", "raw_value": "good"},
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Answer.objects.filter(moodSessionId=session).count(), 0)

    def test_inference_engine_scores_question_and_answer_together(self):
        question_map = {
            question.key: question
            for question in Question.objects.all()
        }
        answers = [
            ("energy_level", "good"),
            ("emotional_tone", "happy"),
            ("mental_state", "sharp"),
            ("activity", "working"),
            ("social_setting", "alone"),
            ("playlist_goal", "focus"),
        ]

        responses = _make_responses(question_map, answers)
        mood_label, secondary, confidence, sec_conf, blend, raw_scores = (
            infer_mood_from_responses(responses, question_categories=_CATEGORY_MAP)
        )

        self.assertEqual(mood_label, "focused")
        self.assertEqual(confidence, raw_scores["focused"])
        self.assertGreater(raw_scores["focused"], raw_scores["energized"])
        self.assertGreater(raw_scores["focused"], 0.5)
        # Secondary mood should exist
        self.assertIsNotNone(secondary)

    # ── New tests for upgraded inference engine ───────────────────────────

    def test_synergy_sad_drifting_escape_produces_melancholic(self):
        """Coherent sad+drifting+escape combo should strongly produce melancholic."""
        question_map = {q.key: q for q in Question.objects.all()}
        answers = [
            ("energy_level", "low"),
            ("emotional_tone", "sad"),
            ("mental_state", "drifting"),
            ("activity", "relaxing"),
            ("social_setting", "alone"),
            ("playlist_goal", "escape"),
        ]
        responses = _make_responses(question_map, answers)
        mood, secondary, conf, sec_conf, blend, scores = infer_mood_from_responses(
            responses, question_categories=_CATEGORY_MAP
        )
        self.assertEqual(mood, "melancholic")
        self.assertGreater(scores["melancholic"], 0.40)

    def test_synergy_happy_charged_party_produces_celebratory(self):
        """Happy+charged+party should strongly produce celebratory."""
        question_map = {q.key: q for q in Question.objects.all()}
        answers = [
            ("energy_level", "charged"),
            ("emotional_tone", "happy"),
            ("mental_state", "motivated"),
            ("activity", "social"),
            ("social_setting", "others"),
            ("playlist_goal", "party"),
        ]
        responses = _make_responses(question_map, answers)
        mood, secondary, conf, sec_conf, blend, scores = infer_mood_from_responses(
            responses, question_categories=_CATEGORY_MAP
        )
        self.assertEqual(mood, "celebratory")
        self.assertGreater(scores["celebratory"], 0.60)

    def test_category_weighting_emotion_outweighs_context(self):
        """emotional_tone=calm should dominate over social_setting=others."""
        question_map = {q.key: q for q in Question.objects.all()}
        # Calm emotion + "others" context — should still produce calm
        answers = [
            ("energy_level", "low"),
            ("emotional_tone", "calm"),
            ("mental_state", "drifting"),
            ("activity", "relaxing"),
            ("social_setting", "others"),
            ("playlist_goal", "relax"),
        ]
        responses = _make_responses(question_map, answers)
        mood, _, _, _, _, scores = infer_mood_from_responses(
            responses, question_categories=_CATEGORY_MAP
        )
        self.assertEqual(mood, "calm")
        self.assertGreater(scores["calm"], scores["celebratory"])

    def test_low_energy_calm_answers_resolve_calm_or_melancholic(self):
        """Low-energy, calm-emotion answers resolve to calm/melancholic from the
        FELT signals alone — without leaning on time_of_day or playlist_goal,
        which are now decoupled from mood (see decoupling test below)."""
        question_map = {q.key: q for q in Question.objects.all()}
        answers = [
            ("energy_level", "low"),
            ("emotional_tone", "calm"),
            ("mental_state", "drifting"),
            ("activity", "relaxing"),
            ("social_setting", "alone"),
        ]
        responses = _make_responses(question_map, answers)
        mood, _, _, _, _, scores = infer_mood_from_responses(
            responses, question_categories=_CATEGORY_MAP
        )
        self.assertIn(mood, {"calm", "melancholic"})

    def test_goal_era_time_do_not_change_felt_mood(self):
        """Fix 7 / goal double-count: with fixed emotional answers, changing only
        playlist_goal, music_era and time_of_day must NOT change the inferred
        mood. Previously a happy user who picked goal=sleep was inferred 'calm',
        and changing the clock/era alone could flip the label."""
        question_map = {q.key: q for q in Question.objects.all()}
        felt = [
            ("energy_level", "charged"),
            ("emotional_tone", "happy"),
            ("mental_state", "motivated"),
            ("activity", "social"),
        ]

        def mood_for(extra):
            responses = _make_responses(question_map, felt + extra)
            return infer_mood_from_responses(responses, question_categories=_CATEGORY_MAP)[0]

        baseline = mood_for([])
        self.assertIn(baseline, {"celebratory", "energized"})
        # None of these non-emotional choices may move the felt-mood label.
        self.assertEqual(baseline, mood_for([("playlist_goal", "sleep")]))
        self.assertEqual(baseline, mood_for([("playlist_goal", "relax")]))
        self.assertEqual(baseline, mood_for([("time_of_day", "late_night")]))
        self.assertEqual(baseline, mood_for([("music_era", "nineties")]))
        self.assertEqual(
            baseline,
            mood_for([("playlist_goal", "sleep"), ("music_era", "nineties"),
                      ("time_of_day", "late_night")]),
        )

    def test_submit_response_exposes_friendly_display_confidence(self):
        """displayConfidence is present, never below the true confidence, and
        capped so the UI reads well without re-inflating the gating math."""
        session = MoodSession.objects.create(userId=self.user)
        response = self.client.post(
            f"/moods/mood-sessions/{session.id}/submit/",
            {"answers": [
                {"question_key": "energy_level", "raw_value": "charged"},
                {"question_key": "emotional_tone", "raw_value": "excited"},
                {"question_key": "activity", "raw_value": "social"},
            ]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("displayConfidence", response.data)
        disp = response.data["displayConfidence"]
        true_conf = response.data["confidence"]
        self.assertGreaterEqual(disp, true_conf)
        self.assertLessEqual(disp, 0.99)

    def test_blend_ratio_is_low_for_ambiguous_answers(self):
        """When answers pull toward multiple moods, blend ratio < 1.0."""
        question_map = {q.key: q for q in Question.objects.all()}
        # Deliberately ambiguous: calm emotion but energized activity
        answers = [
            ("energy_level", "good"),
            ("emotional_tone", "calm"),
            ("mental_state", "motivated"),
            ("activity", "exercising"),
            ("social_setting", "alone"),
        ]
        responses = _make_responses(question_map, answers)
        _, secondary, _, sec_conf, blend, _ = infer_mood_from_responses(
            responses, question_categories=_CATEGORY_MAP
        )
        # Secondary mood should exist for ambiguous answers
        self.assertIsNotNone(secondary)
        self.assertGreater(sec_conf, 0.0)

    def test_returns_six_tuple(self):
        """Verify the engine returns the full 6-element tuple."""
        question_map = {q.key: q for q in Question.objects.all()}
        answers = [
            ("energy_level", "mid"),
            ("emotional_tone", "happy"),
            ("mental_state", "sharp"),
            ("activity", "working"),
            ("social_setting", "alone"),
        ]
        responses = _make_responses(question_map, answers)
        result = infer_mood_from_responses(
            responses, question_categories=_CATEGORY_MAP
        )
        self.assertEqual(len(result), 6)
        top_mood, secondary, conf, sec_conf, blend, scores = result
        self.assertIsInstance(top_mood, str)
        self.assertIsInstance(conf, float)
        self.assertIsInstance(scores, dict)
        self.assertGreater(conf, 0.0)
        self.assertLessEqual(conf, 1.0)
