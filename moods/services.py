from __future__ import annotations

from math import exp

from django.db import transaction
from django.utils import timezone

from moods.constants import OPTION_WEIGHTS, QUESTION_WEIGHTS
from moods.models import Answer, MoodInference, MoodSession, Question


def start_session(user) -> MoodSession:
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


def _normalise_value(raw_value: str, question: Question) -> float:
    if question.inputType == Question.InputTypeChoices.SLIDER:
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Question '{question.key}' expects a float, got '{raw_value}'."
            ) from exc
        if not 0.0 <= value <= 1.0:
            raise ValueError(
                f"Question '{question.key}' value must be between 0.0 and 1.0, got {value}."
            )
        return value

    if question.inputType == Question.InputTypeChoices.SELECT:
        if raw_value not in OPTION_WEIGHTS:
            valid = sorted(OPTION_WEIGHTS.keys())
            raise ValueError(
                f"Unknown option '{raw_value}' for question '{question.key}'. Valid options: {valid}"
            )
        return OPTION_WEIGHTS[raw_value]

    raise ValueError(f"Unsupported input type '{question.inputType}'.")


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
                value=_normalise_value(raw_value, question),
            )
        )

    Answer.objects.bulk_create(rows)


def _infer_mood(session: MoodSession) -> MoodInference:
    existing = MoodInference.objects.filter(moodSessionId=session).first()
    if existing:
        return existing

    scores = {label: 0.0 for label in _all_mood_labels()}
    answers = session.answer.select_related("questionId").all()

    for answer in answers:
        for mood_label, weight in QUESTION_WEIGHTS.get(answer.questionId.key, {}).items():
            scores[mood_label] += weight * answer.value

    exp_scores = {mood: exp(score) for mood, score in scores.items()}
    total = sum(exp_scores.values())
    probabilities = {
        mood: round(score / total, 4)
        for mood, score in exp_scores.items()
    }
    top_mood = max(probabilities, key=probabilities.get)

    return MoodInference.objects.create(
        moodSessionId=session,
        moodLabel=top_mood,
        confidence=probabilities[top_mood],
        rawScores=probabilities,
    )


def _close_session(session: MoodSession) -> None:
    now = timezone.now()
    session.endedAt = now
    session.durationSeconds = int((now - session.startedAt).total_seconds())
    session.save(update_fields=["endedAt", "durationSeconds"])


def _all_mood_labels() -> list[str]:
    return [choice[0] for choice in MoodInference.MoodChoices.choices]
