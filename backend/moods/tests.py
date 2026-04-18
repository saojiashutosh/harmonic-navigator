from rest_framework import status
from rest_framework.test import APITestCase

from moods.inference import build_weight_key, infer_mood_from_responses, normalise_answer_value
from moods.constants import QUESTION_DEFINITIONS
from moods.models import Answer, MoodInference, MoodSession, Question
from users.models import Users


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
                    {"question_key": "music_preference", "raw_value": "lyrics"},
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Answer.objects.filter(moodSessionId=session).count(), 6)

        inference = MoodInference.objects.get(moodSessionId=session)
        self.assertEqual(response.data["id"], str(inference.id))
        self.assertEqual(response.data["moodLabel"], inference.moodLabel)
        self.assertEqual(inference.moodLabel, "focused")
        self.assertIn("is_high_confidence", response.data)

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
            ("music_preference", "lyrics"),
            ("playlist_goal", "focus"),
        ]

        responses = []
        for key, raw_value in answers:
            question = question_map[key]
            responses.append(
                {
                    "weight_key": build_weight_key(question, raw_value),
                    "value": normalise_answer_value(raw_value, question),
                }
            )

        mood_label, confidence, raw_scores = infer_mood_from_responses(responses)

        self.assertEqual(mood_label, "focused")
        self.assertEqual(confidence, raw_scores["focused"])
        self.assertGreater(raw_scores["focused"], raw_scores["energized"])
        self.assertGreater(raw_scores["focused"], 0.5)
