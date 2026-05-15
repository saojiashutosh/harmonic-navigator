"""Business logic for group listening sessions.

The blending engine: every participant takes their own mood survey, producing
a MoodInference (mood label + rawScores per mood + confidence). To turn N
individual inferences into one shared playlist we:

1. Sum the per-mood rawScores across all participants, weighting each
   participant's contribution by their own confidence. The mood with the
   highest summed score becomes the group's primary mood; the runner-up
   becomes the secondary, which the playlist engine already uses for
   diversity mixing.

2. Merge each participant's answer to the preference questions
   (language, style, era, etc.) using a per-question strategy — union for
   multi-select languages, most-common-vote for single-selects, and
   most-restrictive for safety toggles like `social_setting=kids`.

3. Build a synthetic MoodSession + MoodInference owned by the host that
   the existing playlist engine can consume unchanged. This means group
   playlists support every feature regular playlists do — expand, save,
   add-track — for free.
"""

from __future__ import annotations

import json
import secrets
import string
from collections import Counter, defaultdict
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from moods.models import Answer, MoodInference, MoodSession, Question
from playlists.constants import REGISTERED_PLAYLIST_SIZE
from playlists.models import Playlist
from playlists.services import build_playlist_for_session

from .models import GroupParticipant, GroupSession

GROUP_PLAYLIST_SIZE = REGISTERED_PLAYLIST_SIZE
GROUP_TTL_HOURS = 24
MAX_PARTICIPANTS = 6
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no ambiguous chars (0/O/1/I)
_CODE_LENGTH = 6

# Per-question merge strategy when blending multiple participants' surveys
# into a single synthetic survey for the engine to consume.
#  - union_list: combine all picks into a JSON list (engine accepts these)
#  - majority:   most common value across participants, ties broken arbitrarily
#  - safest:     pick the most restrictive value (used for explicit-content gates)
_MERGE_STRATEGY = {
    "music_language": "union_list",
    "music_style":    "majority",
    "music_era":      "majority",
    "music_preference": "majority",
    "playlist_goal":  "majority",
    "preferred_artist": "majority",
    "time_of_day":    "majority",
    "social_setting": "safest",  # kids/meeting wins over chill
}
_SAFEST_RANK = {"kids": 0, "meeting": 1, "study": 2, "chill": 3, "party": 4}


def generate_unique_code() -> str:
    """Return a join code that isn't currently in use by an active session."""
    for _ in range(20):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
        if not GroupSession.objects.filter(code=code).exists():
            return code
    raise RuntimeError("Could not allocate a unique group code.")


def create_group(*, host_user, host_display_name: str) -> tuple[GroupSession, GroupParticipant]:
    """Create a new group session with the caller as host participant."""
    with transaction.atomic():
        session = GroupSession.objects.create(
            code=generate_unique_code(),
            hostId=host_user if host_user and not host_user.is_anonymous else None,
            status=GroupSession.StatusChoices.PENDING,
            expiresAt=timezone.now() + timedelta(hours=GROUP_TTL_HOURS),
        )
        host = GroupParticipant.objects.create(
            groupSessionId=session,
            userId=host_user if host_user and not host_user.is_anonymous else None,
            displayName=host_display_name.strip()[:64] or "host",
            isHost=True,
        )
    return session, host


def join_group(*, code: str, user, display_name: str) -> tuple[GroupSession, GroupParticipant]:
    """Attach a new participant to an existing pending group session."""
    code = (code or "").strip().upper()
    try:
        session = GroupSession.objects.get(code=code)
    except GroupSession.DoesNotExist:
        raise ValueError("That group code doesn't exist.")

    if session.status != GroupSession.StatusChoices.PENDING:
        raise ValueError("That group has already finished — start a new one.")
    if session.expiresAt and session.expiresAt < timezone.now():
        raise ValueError("That group code has expired.")
    if session.participants.count() >= MAX_PARTICIPANTS:
        raise ValueError(f"This group is full (max {MAX_PARTICIPANTS}).")

    participant = GroupParticipant.objects.create(
        groupSessionId=session,
        userId=user if user and not user.is_anonymous else None,
        displayName=display_name.strip()[:64] or "guest",
        isHost=False,
    )
    return session, participant


def attach_mood_session(
    *,
    group: GroupSession,
    participant: GroupParticipant,
    mood_session: MoodSession,
) -> GroupParticipant:
    """Link a participant's completed survey to the group and mark them ready."""
    if participant.groupSessionId_id != group.id:
        raise ValueError("That participant does not belong to this group.")
    if not MoodInference.objects.filter(moodSessionId=mood_session).exists():
        raise ValueError("That mood session has no inference yet.")

    participant.moodSessionId = mood_session
    participant.isReady = True
    participant.save(update_fields=["moodSessionId", "isReady"])
    return participant


def generate_group_playlist(group: GroupSession) -> Playlist:
    """Blend all ready participants' surveys and build one shared playlist."""
    if group.status == GroupSession.StatusChoices.GENERATED and group.playlistId_id:
        return group.playlistId

    ready = (
        group.participants.filter(isReady=True)
        .select_related("moodSessionId")
        .all()
    )
    if len(ready) < 1:
        raise ValueError("At least one participant must be ready before blending.")

    inferences = [
        MoodInference.objects.filter(moodSessionId=p.moodSessionId).first()
        for p in ready
        if p.moodSessionId_id is not None
    ]
    inferences = [inf for inf in inferences if inf is not None]
    if len(inferences) < 1:
        raise ValueError("No valid mood inferences to blend.")

    primary, secondary, blend_ratio, blended_confidence = _blend_inferences(inferences)
    merged_answers = _merge_answer_maps(ready)

    with transaction.atomic():
        synthetic_session = _build_synthetic_session(
            host_user=group.hostId,
            merged_answers=merged_answers,
            primary=primary,
            secondary=secondary,
            blend_ratio=blend_ratio,
            confidence=blended_confidence,
        )
        playlist = build_playlist_for_session(
            synthetic_session, limit=GROUP_PLAYLIST_SIZE
        )

        group.playlistId = playlist
        group.blendedMoodLabel = primary
        group.status = GroupSession.StatusChoices.GENERATED
        group.save(update_fields=["playlistId", "blendedMoodLabel", "status", "updatedAt"])

    return playlist


# ── Internals ───────────────────────────────────────────────────────────────


def _blend_inferences(inferences) -> tuple[str, str | None, float, float]:
    """Confidence-weighted sum of per-mood scores.

    Returns (primary_mood, secondary_mood, blend_ratio, avg_confidence).
    blend_ratio is the share of primary_score / (primary + secondary), so
    a tighter agreement among participants yields a more mood-pure playlist.
    """
    totals: dict[str, float] = defaultdict(float)
    for inf in inferences:
        weight = max(inf.confidence or 0.5, 0.1)
        scores = inf.rawScores or {}
        # Fallback so a participant with an empty rawScores still contributes
        # via their declared mood label.
        if not scores and inf.moodLabel:
            scores = {inf.moodLabel: 1.0}
        for mood, score in scores.items():
            totals[mood] += float(score) * weight

    if not totals:
        # Degenerate case: nobody had any scores. Fall back to the most common
        # mood label and treat blend_ratio as fully primary.
        labels = [inf.moodLabel for inf in inferences if inf.moodLabel]
        primary = Counter(labels).most_common(1)[0][0] if labels else "calm"
        return primary, None, 1.0, _avg_confidence(inferences)

    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    primary, primary_score = ranked[0]
    secondary, secondary_score = ranked[1] if len(ranked) > 1 else (None, 0.0)

    denom = primary_score + secondary_score
    blend_ratio = primary_score / denom if denom else 1.0
    # Keep some daylight between primary and secondary so the engine still
    # produces a coherent room rather than a chaotic 50/50 mix.
    blend_ratio = max(0.55, min(blend_ratio, 1.0))
    return primary, secondary, blend_ratio, _avg_confidence(inferences)


def _avg_confidence(inferences) -> float:
    if not inferences:
        return 0.0
    return sum((inf.confidence or 0.0) for inf in inferences) / len(inferences)


def _merge_answer_maps(participants) -> dict[str, object]:
    """Collect each participant's rawValues per question key, then merge per strategy."""
    per_key: dict[str, list] = defaultdict(list)
    for p in participants:
        if p.moodSessionId_id is None:
            continue
        for ans in p.moodSessionId.answer.select_related("questionId").all():
            per_key[ans.questionId.key].append(ans.rawValue)

    merged: dict[str, object] = {}
    for key, raw_values in per_key.items():
        strategy = _MERGE_STRATEGY.get(key, "majority")
        merged[key] = _apply_strategy(strategy, raw_values, key)
    return merged


def _apply_strategy(strategy: str, raw_values: list, key: str):
    parsed = [_parse_raw(v) for v in raw_values]

    if strategy == "union_list":
        union: list[str] = []
        seen = set()
        for values in parsed:
            for v in (values if isinstance(values, list) else [values]):
                v_str = str(v).strip()
                if v_str and v_str.lower() != "no_preference" and v_str not in seen:
                    seen.add(v_str)
                    union.append(v_str)
        if not union:
            return ""
        return json.dumps(union) if len(union) > 1 else union[0]

    if strategy == "safest" and key == "social_setting":
        flat = [v for values in parsed for v in (values if isinstance(values, list) else [values])]
        flat = [str(v).strip() for v in flat if v]
        if not flat:
            return ""
        flat.sort(key=lambda v: _SAFEST_RANK.get(v, 99))
        return flat[0]

    # majority
    flat = [str(v).strip() for values in parsed for v in (values if isinstance(values, list) else [values]) if v]
    flat = [v for v in flat if v and v.lower() != "no_preference"]
    if not flat:
        return ""
    return Counter(flat).most_common(1)[0][0]


def _parse_raw(raw_value):
    if raw_value is None:
        return ""
    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed, list):
            return parsed
        return str(parsed)
    except (json.JSONDecodeError, TypeError, ValueError):
        return str(raw_value)


def _build_synthetic_session(
    *,
    host_user,
    merged_answers: dict[str, object],
    primary: str,
    secondary: str | None,
    blend_ratio: float,
    confidence: float,
) -> MoodSession:
    """Persist a MoodSession + Answers + MoodInference so the playlist engine,
    which reads everything off the session, can run unchanged.

    We persist (rather than passing an in-memory object) because the engine
    fetches answers via `session.answer.select_related(...)` — that reverse
    relation only works for saved rows.
    """
    owner = host_user if host_user and getattr(host_user, "is_authenticated", False) else None
    session = MoodSession.objects.create(userId=owner)

    # Persist merged answers, skipping any unknown keys (so adding new
    # question keys in the moods app doesn't break the group blender).
    question_map = {
        q.key: q
        for q in Question.objects.filter(key__in=list(merged_answers.keys()))
    }
    rows = []
    for key, value in merged_answers.items():
        question = question_map.get(key)
        if question is None:
            continue
        raw_str = value if isinstance(value, str) else json.dumps(value)
        rows.append(
            Answer(
                moodSessionId=session,
                questionId=question,
                rawValue=raw_str,
                value=0.5,
            )
        )
    if rows:
        Answer.objects.bulk_create(rows)

    MoodInference.objects.create(
        moodSessionId=session,
        moodLabel=primary,
        confidence=confidence,
        rawScores={primary: 1.0, **({secondary: max(0.0, 1.0 - blend_ratio)} if secondary else {})},
        secondaryMoodLabel=secondary,
        secondaryConfidence=(1.0 - blend_ratio) if secondary else None,
        moodBlendRatio=blend_ratio,
    )

    # Close the session so it mirrors a normal "submitted" survey.
    now = timezone.now()
    session.endedAt = now
    session.durationSeconds = 0
    session.save(update_fields=["endedAt", "durationSeconds"])

    return session
