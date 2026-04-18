from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from moods.inference import (
    build_weight_key,
    infer_mood_from_responses,
    normalise_answer_value,
)
from moods.models import Answer, MoodInference, MoodSession, Question


def start_session(user) -> MoodSession:
    # Handle Django AnonymousUser by setting to None for guest sessions
    if user and user.is_anonymous:
        user = None
    return MoodSession.objects.create(userId=user)


def submit_answers(session: MoodSession, answers: list[dict]) -> MoodInference:
    with transaction.atomic():
        _validate_answers(answers)
        _save_answers(session, answers)
        inference = _infer_mood(session)
        _close_session(session)
        return inference


def get_active_questions() -> list[Question]:
    return list(Question.objects.filter(isActive=True).order_by("order"))


def get_session_result(session: MoodSession) -> MoodInference | None:
    return MoodInference.objects.filter(moodSessionId=session).first()


def _validate_answers(answers: list[dict]) -> None:
    if not answers:
        raise ValueError("At least one answer is required.")

    keys = [answer["question_key"] for answer in answers]
    if len(keys) != len(set(keys)):
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        raise ValueError(f"Duplicate question keys: {duplicates}")

    active_keys = set(
        Question.objects.filter(key__in=keys, isActive=True).values_list("key", flat=True)
    )
    unknown = sorted(set(keys) - active_keys)
    if unknown:
        raise ValueError(f"Unknown or inactive question keys: {unknown}")


def _save_answers(session: MoodSession, answers: list[dict]) -> None:
    question_map = {
        question.key: question
        for question in Question.objects.filter(
            key__in=[answer["question_key"] for answer in answers],
            isActive=True,
        )
    }

    rows = []
    for answer in answers:
        question = question_map[answer["question_key"]]
        raw_value = str(answer["raw_value"])
        rows.append(
            Answer(
                moodSessionId=session,
                questionId=question,
                rawValue=raw_value,
                value=normalise_answer_value(raw_value, question),
            )
        )

    Answer.objects.bulk_create(rows)


def _infer_mood(session: MoodSession) -> MoodInference:
    existing = MoodInference.objects.filter(moodSessionId=session).first()
    if existing:
        return existing

    answers = session.answer.select_related("questionId").all()
    responses = [
        {
            "weight_key": build_weight_key(answer.questionId, answer.rawValue),
            "value": answer.value,
        }
        for answer in answers
    ]
    top_mood, confidence, probabilities = infer_mood_from_responses(responses)

    return MoodInference.objects.create(
        moodSessionId=session,
        moodLabel=top_mood,
        confidence=confidence,
        rawScores=probabilities,
    )


def _close_session(session: MoodSession) -> None:
    now = timezone.now()
    session.endedAt = now
    session.durationSeconds = int((now - session.startedAt).total_seconds())
    session.save(update_fields=["endedAt", "durationSeconds"])
