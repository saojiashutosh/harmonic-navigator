from __future__ import annotations

import logging
from math import exp

from moods.constants import (
    CATEGORY_WEIGHTS,
    OPTION_WEIGHTS,
    QUESTION_WEIGHTS,
    SYNERGY_BONUSES,
)
from moods.models import MoodInference, Question

logger = logging.getLogger(__name__)

LOGIT_SCALE = 2.4

# Below this confidence, the engine blends top-2 moods equally.
LOW_CONFIDENCE_THRESHOLD = 0.40


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
    *,
    question_categories: dict[str, str] | None = None,
) -> tuple[str, str | None, float, float, float, dict[str, float]]:
    """Infer mood from a list of response dicts.

    Parameters
    ----------
    responses : list[dict]
        Each dict must have ``weight_key`` (str) and ``value`` (float).
        Optionally ``raw_value`` (str) for synergy detection and
        ``category`` (str) for per-category weighting.
    question_categories : dict | None
        Mapping of question_key → category string.  Used to look up the
        category weight when the response dict does not include it.

    Returns
    -------
    tuple of (top_mood, secondary_mood, confidence, secondary_confidence,
              mood_blend_ratio, probabilities)
    """
    question_categories = question_categories or {}
    scores = {label: 0.0 for label in all_mood_labels()}

    # ── Collect raw_values for synergy detection ──────────────────────────
    all_raw_values: set[str] = set()

    for response in responses:
        weight_key: str = response["weight_key"]
        value: float = response["value"]

        # Determine category weight
        category = response.get("category")
        if not category:
            # Derive category from weight_key → question_key
            question_key = "_".join(weight_key.split("_")[:-1])
            # Try progressively shorter prefixes (handles keys like
            # "energy_level" where the raw_value is the last segment)
            parts = weight_key.split("_")
            for split_at in range(len(parts) - 1, 0, -1):
                candidate = "_".join(parts[:split_at])
                if candidate in question_categories:
                    question_key = candidate
                    break
            category = question_categories.get(question_key, "")

        cat_weight = CATEGORY_WEIGHTS.get(category, 1.0)

        for mood_label, weight in QUESTION_WEIGHTS.get(weight_key, {}).items():
            scores[mood_label] += weight * value * cat_weight

        # Track raw_values for synergy
        raw_value = response.get("raw_value")
        if raw_value:
            all_raw_values.add(raw_value)

    # ── Apply synergy bonuses ─────────────────────────────────────────────
    for trigger_set, mood_label, bonus in SYNERGY_BONUSES:
        if trigger_set.issubset(all_raw_values) and mood_label in scores:
            scores[mood_label] += bonus
            logger.debug(
                "Synergy bonus %.2f for %s (trigger: %s)",
                bonus, mood_label, trigger_set,
            )

    # ── Softmax ───────────────────────────────────────────────────────────
    exp_scores = {mood: exp(score * LOGIT_SCALE) for mood, score in scores.items()}
    total = sum(exp_scores.values())
    probabilities = {
        mood: round(score / total, 4)
        for mood, score in exp_scores.items()
    }

    # ── Top-2 moods ───────────────────────────────────────────────────────
    sorted_moods = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
    top_mood, top_conf = sorted_moods[0]
    secondary_mood, secondary_conf = sorted_moods[1] if len(sorted_moods) > 1 else (None, 0.0)

    # ── Low-confidence blending ───────────────────────────────────────────
    if top_conf < LOW_CONFIDENCE_THRESHOLD and secondary_mood is not None:
        mood_blend_ratio = 0.50  # Equal blend
    elif secondary_mood is not None and (top_conf - secondary_conf) < 0.10:
        # Very close race — partial blend
        mood_blend_ratio = 0.70
    else:
        mood_blend_ratio = 1.00  # Pure primary

    return (
        top_mood,
        secondary_mood,
        top_conf,
        secondary_conf,
        mood_blend_ratio,
        probabilities,
    )


def all_mood_labels() -> list[str]:
    return [choice[0] for choice in MoodInference.MoodChoices.choices]
