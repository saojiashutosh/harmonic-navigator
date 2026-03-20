from rest_framework import status
from rest_framework.test import APITestCase

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
                    key="energy_level",
                    text="How energetic do you feel?",
                    category=Question.CategoryChoices.ENERGY,
                    inputType=Question.InputTypeChoices.SLIDER,
                    order=1,
                    isActive=True,
                ),
                Question(
                    key="activity_working",
                    text="What are you doing?",
                    category=Question.CategoryChoices.ACTIVITY,
                    inputType=Question.InputTypeChoices.SELECT,
                    options=["working", "other"],
                    order=2,
                    isActive=True,
                ),
            ]
        )

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    def test_create_session(self):
        response = self.client.post("/api/moods/mood-sessions/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MoodSession.objects.count(), 1)
        self.assertEqual(MoodSession.objects.get().userId, self.user)

    def test_submit_answers_creates_answers_and_inference(self):
        session = MoodSession.objects.create(userId=self.user)

        response = self.client.post(
            f"/api/moods/mood-sessions/{session.id}/submit/",
            {
                "answers": [
                    {"question_key": "energy_level", "raw_value": "0.8"},
                    {"question_key": "activity_working", "raw_value": "working"},
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Answer.objects.filter(moodSessionId=session).count(), 2)

        inference = MoodInference.objects.get(moodSessionId=session)
        self.assertEqual(response.data["id"], str(inference.id))
        self.assertEqual(response.data["moodLabel"], inference.moodLabel)
        self.assertIn("is_high_confidence", response.data)

        session.refresh_from_db()
        self.assertIsNotNone(session.endedAt)
        self.assertIsNotNone(session.durationSeconds)

    def test_submit_rejects_duplicate_question_keys(self):
        session = MoodSession.objects.create(userId=self.user)

        response = self.client.post(
            f"/api/moods/mood-sessions/{session.id}/submit/",
            {
                "answers": [
                    {"question_key": "energy_level", "raw_value": "0.3"},
                    {"question_key": "energy_level", "raw_value": "0.6"},
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Answer.objects.filter(moodSessionId=session).count(), 0)
