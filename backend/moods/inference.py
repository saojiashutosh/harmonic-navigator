from __future__ import annotations

from math import exp

from moods.constants import OPTION_WEIGHTS, QUESTION_WEIGHTS
from moods.models import MoodInference, Question

LOGIT_SCALE = 2.4


def normalise_answer_value(raw_value: str, question: Question) -> float:
    if question.inputType == Question.InputTypeChoices.SELECT:
        if raw_value not in OPTION_WEIGHTS:
            valid = sorted(OPTION_WEIGHTS.keys())
            raise ValueError(
                f"Unknown option '{raw_value}' for question '{question.key}'. Valid options: {valid}"
            )
        return OPTION_WEIGHTS[raw_value]
    if question.inputType == Question.InputTypeChoices.TEXT:
        return 1.0 if raw_value.strip() else 0.0

    raise ValueError(f"Unsupported input type '{question.inputType}'.")


def build_weight_key(question: Question, raw_value: str) -> str:
    return f"{question.key}_{raw_value}"


def infer_mood_from_responses(
    responses: list[dict[str, object]],
) -> tuple[str, float, dict[str, float]]:
    scores = {label: 0.0 for label in all_mood_labels()}

    for response in responses:
        weight_key = response["weight_key"]
        value = response["value"]
        for mood_label, weight in QUESTION_WEIGHTS.get(weight_key, {}).items():
            scores[mood_label] += weight * value

    exp_scores = {mood: exp(score * LOGIT_SCALE) for mood, score in scores.items()}
    total = sum(exp_scores.values())
    probabilities = {
        mood: round(score / total, 4)
        for mood, score in exp_scores.items()
    }
    top_mood = max(probabilities, key=probabilities.get)
    return top_mood, probabilities[top_mood], probabilities


def all_mood_labels() -> list[str]:
    return [choice[0] for choice in MoodInference.MoodChoices.choices]
