"""Groq-powered mood inference — free-tier LLM fallback when rule-based
confidence is low.  Uses llama-3.1-8b-instant via Groq's OpenAI-compatible
REST API; no extra Python package needed beyond `requests` (already present).

Get a free API key at https://console.groq.com (no credit card required).
Set GROQ_API_KEY in .env to enable; leave blank to skip AI inference.
"""
from __future__ import annotations

import json
import logging

import requests
from django.core.cache import cache

from helpers.cache_utils import AI_MOOD_TTL, ai_mood_cache_key

logger = logging.getLogger(__name__)

MOOD_LABELS = ["energized", "focused", "melancholic", "anxious", "celebratory", "calm"]

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_MODEL = "llama-3.1-8b-instant"

_MOOD_DESCRIPTIONS = {
    "energized":   "high energy, motivated, ready to move or accomplish things",
    "focused":     "concentrated, sharp, working or studying, needs minimal distraction",
    "melancholic": "low or sad mood, nostalgic, introspective, seeking emotional depth",
    "anxious":     "tense, restless, worried, overthinking, needs calming music",
    "celebratory": "joyful, festive, social, happy, party-ready",
    "calm":        "peaceful, relaxed, meditative, winding down, needs gentle music",
}

_SYSTEM_PROMPT = (
    "You are a concise music-mood analyst. Given a user's self-reported answers, "
    "identify which single mood label fits best for a music recommendation engine.\n\n"
    "Mood labels:\n"
    + "\n".join(f"- {lbl}: {desc}" for lbl, desc in _MOOD_DESCRIPTIONS.items())
    + "\n\nRules:\n"
    "1. Output ONLY valid JSON — no markdown, no extra text.\n"
    "2. 'mood' must be one of the exact labels above.\n"
    "3. 'confidence' is 0.0–1.0 (how clearly the answers point to one mood).\n"
    "4. 'reasoning' is one short sentence."
)

_USER_TEMPLATE = (
    "User's answers:\n{answers}\n\n"
    'Reply: {{"mood":"<label>","confidence":<float>,"reasoning":"<sentence>"}}'
)

_QUESTION_LABELS: dict[str, str] = {
    "energy_level":      "Energy level",
    "emotional_tone":    "Emotional tone",
    "mental_state":      "Mental state / headspace",
    "activity":          "Current activity",
    "social_setting":    "Social setting",
    "music_language":    "Preferred song language(s)",
    "playlist_goal":     "Playlist goal",
    "preferred_artist":  "Preferred artist",
    "time_of_day":       "Time of day",
    "nostalgia_craving": "Nostalgia vs discovery",
}


def ai_infer_mood(answers: list[dict]) -> tuple[str, float, str] | None:
    """Use Groq (free Llama 3) to infer mood from user answers.

    Parameters
    ----------
    answers : list of dicts with ``question_key`` and ``raw_value`` keys.

    Returns
    -------
    (mood_label, confidence, reasoning) on success, None on any failure.
    The caller must handle None gracefully.
    """
    key = ai_mood_cache_key(answers)
    cached = cache.get(key)
    if cached is not None:
        logger.debug("Groq inference cache hit for key %s", key)
        return tuple(cached)

    try:
        from django.conf import settings

        api_key = getattr(settings, "GROQ_API_KEY", None) or ""
        api_key = api_key.strip()
        if not api_key:
            return None

        lines = []
        for a in answers:
            key = a.get("question_key", "")
            label = _QUESTION_LABELS.get(key, key.replace("_", " ").title())
            value = str(a.get("raw_value", "")).replace("_", " ").strip()
            if value:
                lines.append(f"• {label}: {value}")

        if not lines:
            return None

        user_prompt = _USER_TEMPLATE.format(answers="\n".join(lines))

        resp = requests.post(
            _GROQ_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": _MODEL,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 150,
                "temperature": 0.1,
            },
            timeout=8,
        )
        resp.raise_for_status()

        raw = resp.json()["choices"][0]["message"]["content"].strip()

        # Strip markdown code fences if the model wraps the JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        mood = str(result.get("mood", "")).strip().lower()
        confidence = float(result.get("confidence", 0.70))
        reasoning = str(result.get("reasoning", "")).strip()

        if mood not in MOOD_LABELS:
            logger.warning("Groq inference returned unknown mood label: %r", mood)
            return None

        confidence = max(0.0, min(1.0, confidence))
        logger.info("Groq inference: mood=%s confidence=%.2f | %s", mood, confidence, reasoning)
        result_tuple = (mood, confidence, reasoning)
        cache.set(key, list(result_tuple), AI_MOOD_TTL)
        return result_tuple

    except Exception as exc:
        logger.warning("Groq mood inference failed (%s): %s", type(exc).__name__, exc)
        return None
