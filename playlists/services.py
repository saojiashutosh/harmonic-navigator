from __future__ import annotations

from django.db import transaction

from feedback.models import TrackMoodScore, UserMoodPreference
from moods.constants import MUSIC_PREFERENCE_OVERRIDES
from moods.models import MoodInference, MoodSession
from tracks.models import Track

from .constants import DEFAULT_PLAYLIST_SIZE, MOOD_TYPE_RATIOS, TARGET_TRACK_ATTRIBUTES
from .models import Playlist, PlaylistTrack


def build_playlist_for_session(
    session: MoodSession,
    *,
    limit: int = DEFAULT_PLAYLIST_SIZE,
) -> Playlist:
    inference = MoodInference.objects.filter(moodSessionId=session).first()
    if inference is None:
        raise ValueError("Mood session has no inference yet.")

    answer_map = {
        answer.questionId.key: answer.rawValue
        for answer in session.answer.select_related("questionId").all()
    }
    social_setting = answer_map.get("social_setting")
    music_preference = answer_map.get("music_preference")
    type_weights = _resolve_type_weights(
        user_id=session.userId_id,
        mood_label=inference.moodLabel,
        music_preference=music_preference,
    )

    candidate_tracks = Track.objects.filter(isActive=True)
    if social_setting in {"kids", "meeting"}:
        candidate_tracks = candidate_tracks.filter(isExplicit=False)

    scored_tracks = []
    for track in candidate_tracks:
        relevance_score = _score_track(
            track=track,
            user_id=session.userId_id,
            mood_label=inference.moodLabel,
            type_weights=type_weights,
            music_preference=music_preference,
        )
        scored_tracks.append((track, relevance_score))

    scored_tracks.sort(key=lambda item: item[1], reverse=True)
    chosen_tracks = scored_tracks[:limit]

    with transaction.atomic():
        playlist = Playlist.objects.create(
            userId=session.userId,
            moodInferenceId=inference,
            moodLabel=inference.moodLabel,
            confidence=inference.confidence,
            status=Playlist.StatusChoices.READY if chosen_tracks else Playlist.StatusChoices.FAILED,
            trackCount=len(chosen_tracks),
        )

        PlaylistTrack.objects.bulk_create(
            [
                PlaylistTrack(
                    playlistId=playlist,
                    trackId=track,
                    position=index,
                    selectionReason=_selection_reason(
                        track=track,
                        mood_label=inference.moodLabel,
                        music_preference=music_preference,
                    ),
                    relevanceScore=score,
                )
                for index, (track, score) in enumerate(chosen_tracks, start=1)
            ]
        )

    return playlist


def _resolve_type_weights(*, user_id, mood_label: str, music_preference: str | None) -> dict[str, float]:
    default_weights = dict(MOOD_TYPE_RATIOS.get(mood_label, MOOD_TYPE_RATIOS["focused"]))
    preference = UserMoodPreference.objects.filter(
        userId_id=user_id,
        moodLabel=mood_label,
    ).first()
    if preference and preference.is_reliable:
        default_weights = {
            "song": preference.songWeight,
            "instrumental": preference.instrumentalWeight,
            "ambient": preference.ambientWeight,
        }

    override = MUSIC_PREFERENCE_OVERRIDES.get(music_preference)
    if override:
        return dict(override)
    return default_weights


def _score_track(*, track: Track, user_id, mood_label: str, type_weights: dict[str, float], music_preference: str | None) -> float:
    score = 0.0

    if track.primaryMood == mood_label:
        score += 0.45
    elif track.primaryMood:
        score += 0.10

    score += type_weights.get(track.type, 0.0) * 0.30

    target = TARGET_TRACK_ATTRIBUTES.get(mood_label)
    if target:
        if track.energy is not None:
            score += max(0.0, 1 - abs(track.energy - target["energy"])) * 0.15
        if track.valence is not None:
            score += max(0.0, 1 - abs(track.valence - target["valence"])) * 0.10

    if music_preference == "lyrics" and not track.isInstrumental:
        score += 0.08
    if music_preference == "no_lyrics" and track.isInstrumental:
        score += 0.10
    if music_preference == "background" and track.type == Track.TypeChoices.AMBIENT:
        score += 0.12

    feedback_score = TrackMoodScore.objects.filter(
        userId_id=user_id,
        trackId=track,
        moodLabel=mood_label,
    ).values_list("score", flat=True).first()
    if feedback_score is not None:
        score += feedback_score * 0.20

    return round(min(score, 1.0), 4)


def _selection_reason(*, track: Track, mood_label: str, music_preference: str | None) -> str:
    if music_preference == "background" and track.type == Track.TypeChoices.AMBIENT:
        return PlaylistTrack.SelectionReason.TAG_MATCH
    if music_preference == "surprise":
        return PlaylistTrack.SelectionReason.NOVELTY
    if track.primaryMood == mood_label:
        return PlaylistTrack.SelectionReason.MOOD_MATCH
    return PlaylistTrack.SelectionReason.FALLBACK
