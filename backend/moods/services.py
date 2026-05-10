from __future__ import annotations

import json
from django.db import transaction
from django.utils import timezone

from moods.ai_inference import ai_infer_mood
from moods.constants import QUESTION_DEFINITIONS
from moods.inference import (
    build_weight_key,
    infer_mood_from_responses,
    normalise_answer_value,
)
from moods.models import Answer, MoodInference, MoodSession, Question

# When rule-based confidence is below this, ask Claude for a second opinion.
_AI_FALLBACK_THRESHOLD = 0.55


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


def _parse_raw_value(raw_value_str: str | None) -> list[str]:
    """Parse a stored rawValue (plain string or JSON array) into a list of values."""
    if not raw_value_str:
        return []
    try:
        parsed = json.loads(raw_value_str)
        if isinstance(parsed, list):
            return [str(v) for v in parsed if v]
        return [str(parsed)] if parsed else []
    except (json.JSONDecodeError, TypeError):
        return [raw_value_str]


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
        raw_value = answer["raw_value"]
        if isinstance(raw_value, list):
            raw_value_str = json.dumps(raw_value)
        else:
            raw_value_str = str(raw_value) if raw_value is not None else ""
        rows.append(
            Answer(
                moodSessionId=session,
                questionId=question,
                rawValue=raw_value_str,
                value=normalise_answer_value(raw_value, question),
            )
        )

    Answer.objects.bulk_create(rows)


# Build a category lookup from QUESTION_DEFINITIONS so we don't need
# an extra DB query.
_QUESTION_CATEGORY_MAP = {
    defn["key"]: defn["category"]
    for defn in QUESTION_DEFINITIONS
}


def _infer_mood(session: MoodSession) -> MoodInference:
    existing = MoodInference.objects.filter(moodSessionId=session).first()
    if existing:
        return existing

    answers = session.answer.select_related("questionId").all()
    responses = []
    for answer in answers:
        raw_values = _parse_raw_value(answer.rawValue)
        if not raw_values:
            continue
        # Divide value evenly across selections so multi-select doesn't over-amplify
        per_value_weight = answer.value / len(raw_values)
        for rv in raw_values:
            responses.append({
                "weight_key": build_weight_key(answer.questionId, rv),
                "value": per_value_weight,
                "raw_value": rv,
                "category": answer.questionId.category,
            })

    (
        top_mood,
        secondary_mood,
        confidence,
        secondary_confidence,
        mood_blend_ratio,
        probabilities,
    ) = infer_mood_from_responses(
        responses,
        question_categories=_QUESTION_CATEGORY_MAP,
    )

    # When rule-based confidence is uncertain, ask Claude to validate / override.
    if confidence < _AI_FALLBACK_THRESHOLD:
        ai_answers = []
        for a in answers:
            raw_values = _parse_raw_value(a.rawValue)
            ai_answers.append({
                "question_key": a.questionId.key,
                "raw_value": ", ".join(raw_values) if raw_values else "",
            })
        ai_result = ai_infer_mood(ai_answers)
        if ai_result is not None:
            ai_mood, ai_confidence, _ = ai_result
            # If AI agrees with rule-based, boost confidence.
            # If AI disagrees, trust AI when its confidence is clearly higher.
            if ai_mood == top_mood:
                confidence = max(confidence, ai_confidence)
            elif ai_confidence > confidence + 0.15:
                # AI picked a different, more confident mood — use it.
                # Demote old top to secondary if it's a different label.
                secondary_mood = top_mood
                secondary_confidence = confidence
                top_mood = ai_mood
                confidence = ai_confidence
                mood_blend_ratio = 0.80

    return MoodInference.objects.create(
        moodSessionId=session,
        moodLabel=top_mood,
        confidence=confidence,
        rawScores=probabilities,
        secondaryMoodLabel=secondary_mood,
        secondaryConfidence=secondary_confidence,
        moodBlendRatio=mood_blend_ratio,
    )


def _close_session(session: MoodSession) -> None:
    now = timezone.now()
    session.endedAt = now
    session.durationSeconds = int((now - session.startedAt).total_seconds())
    session.save(update_fields=["endedAt", "durationSeconds"])
