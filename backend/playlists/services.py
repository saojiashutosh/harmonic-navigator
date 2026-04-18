from __future__ import annotations

from django.db import transaction
from django.db.models import Q

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
    music_language = answer_map.get("music_language")
    music_style = answer_map.get("music_style")
    playlist_goal = answer_map.get("playlist_goal")
    preferred_artist = answer_map.get("preferred_artist")
    type_weights = _resolve_type_weights(
        user_id=session.userId_id,
        mood_label=inference.moodLabel,
        music_preference=music_preference,
    )

    candidate_tracks = _build_candidate_pool(
        mood_label=inference.moodLabel,
        social_setting=social_setting,
        music_preference=music_preference,
        music_language=music_language,
        music_style=music_style,
        preferred_artist=preferred_artist,
        limit=limit,
    )
    feedback_map = _feedback_score_map(
        user_id=session.userId_id,
        mood_label=inference.moodLabel,
        tracks=candidate_tracks,
    )

    scored_tracks = []
    for track in candidate_tracks:
        relevance_score = _score_track(
            track=track,
            mood_label=inference.moodLabel,
            type_weights=type_weights,
            music_preference=music_preference,
            music_language=music_language,
            music_style=music_style,
            playlist_goal=playlist_goal,
            preferred_artist=preferred_artist,
            feedback_map=feedback_map,
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


def _build_candidate_pool(
    *,
    mood_label: str,
    social_setting: str | None,
    music_preference: str | None,
    music_language: str | None,
    music_style: str | None,
    preferred_artist: str | None,
    limit: int,
) -> list[Track]:
    base_qs = Track.objects.select_related("artistId").filter(isActive=True)
    if social_setting in {"kids", "meeting"}:
        base_qs = base_qs.filter(isExplicit=False)

    mood_q = Q(primaryMood=mood_label) if mood_label else Q()
    language_q = _language_query(music_language)
    style_q = _style_query(music_style)
    type_q = _type_query(music_preference)
    artist_q = _artist_query(preferred_artist)

    pool_size = max(limit * 25, 250)
    slice_size = max(limit * 8, 50)
    queries = [
        artist_q & language_q & style_q & type_q & mood_q,
        artist_q & language_q & type_q,
        artist_q & style_q & type_q,
        language_q & style_q & type_q & mood_q,
        language_q & style_q & type_q,
        artist_q & mood_q,
        language_q & mood_q & type_q,
        style_q & mood_q & type_q,
        mood_q & type_q,
        language_q & type_q,
        style_q & type_q,
        artist_q,
        type_q,
        mood_q,
        Q(),
    ]

    selected: list[Track] = []
    seen_ids: set[str] = set()
    for query in queries:
        queryset = base_qs if query == Q() else base_qs.filter(query)
        for track in queryset[:slice_size]:
            track_id = str(track.id)
            if track_id in seen_ids:
                continue
            seen_ids.add(track_id)
            selected.append(track)
            if len(selected) >= pool_size:
                return selected

    return selected


def _feedback_score_map(*, user_id, mood_label: str, tracks: list[Track]) -> dict[str, float]:
    if not user_id or not tracks:
        return {}

    rows = TrackMoodScore.objects.filter(
        userId_id=user_id,
        moodLabel=mood_label,
        trackId_id__in=[track.id for track in tracks],
    ).values_list("trackId_id", "score")
    return {str(track_id): score for track_id, score in rows}


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


def _score_track(
    *,
    track: Track,
    mood_label: str,
    type_weights: dict[str, float],
    music_preference: str | None,
    music_language: str | None,
    music_style: str | None,
    playlist_goal: str | None,
    preferred_artist: str | None,
    feedback_map: dict[str, float],
) -> float:
    score = 0.0

    if track.primaryMood == mood_label:
        score += 0.30
    elif track.primaryMood:
        score += 0.04

    score += type_weights.get(track.type, 0.0) * 0.18

    target = TARGET_TRACK_ATTRIBUTES.get(mood_label)
    if target:
        if track.energy is not None:
            score += max(0.0, 1 - abs(track.energy - target["energy"])) * 0.12
        if track.valence is not None:
            score += max(0.0, 1 - abs(track.valence - target["valence"])) * 0.08

    if music_preference == "lyrics" and not track.isInstrumental:
        score += 0.14
    if music_preference == "no_lyrics" and (track.isInstrumental or track.type != Track.TypeChoices.SONG):
        score += 0.18
    if music_preference == "background" and track.type == Track.TypeChoices.AMBIENT:
        score += 0.22

    score += _taste_score(
        track=track,
        music_language=music_language,
        music_style=music_style,
        playlist_goal=playlist_goal,
        preferred_artist=preferred_artist,
    )

    feedback_score = feedback_map.get(str(track.id))
    if feedback_score is not None:
        score += feedback_score * 0.20

    return round(min(max(score, 0.0), 1.5), 4)


def _taste_score(
    *,
    track: Track,
    music_language: str | None,
    music_style: str | None,
    playlist_goal: str | None,
    preferred_artist: str | None,
) -> float:
    score = 0.0
    language = _normalise(track.language)
    genre = _normalise(track.genre)
    region = _normalise(track.region)
    raga_name = _normalise(track.ragaName)
    classical_form = _normalise(track.classicalForm)
    artist_name = _normalise(getattr(track.artistId, "name", ""))

    requested_language = _normalise(music_language)
    if requested_language and requested_language != "no_preference":
        if requested_language == "instrumental" and track.isInstrumental:
            score += 0.45
        elif requested_language == language:
            score += 0.42
        elif requested_language == "hindi" and genre == "bollywood":
            score += 0.34
        else:
            score -= 0.12

    requested_style = _normalise(music_style)
    if requested_style and requested_style != "no_preference":
        if requested_style == genre:
            score += 0.40
        elif requested_style == "bollywood" and (language == "hindi" or region == "india"):
            score += 0.36
        elif requested_style == "hollywood" and language == "english":
            score += 0.30
        elif requested_style == "classical" and classical_form:
            score += 0.34
        elif requested_style == "raga" and (raga_name or genre == "raga"):
            score += 0.36
        else:
            score -= 0.10

    requested_goal = _normalise(playlist_goal)
    if requested_goal == "focus" and track.primaryMood == "focused":
        score += 0.18
    elif requested_goal in {"relax", "sleep"} and track.primaryMood == "calm":
        score += 0.20
    elif requested_goal == "uplift" and track.primaryMood in {"energized", "celebratory"}:
        score += 0.18
    elif requested_goal == "escape" and track.primaryMood in {"calm", "melancholic"}:
        score += 0.16
    elif requested_goal == "party" and track.primaryMood == "celebratory":
        score += 0.22

    artist_query = _normalise(preferred_artist)
    if artist_query and artist_query not in {"any", "none", "no_preference"}:
        if artist_query in artist_name:
            score += 0.75
        else:
            score -= 0.15

    if track.artistPopularity is not None:
        score += min(track.artistPopularity / 100, 1.0) * 0.05

    return score


def _language_query(music_language: str | None) -> Q:
    requested_language = _normalise(music_language)
    if not requested_language or requested_language == "no_preference":
        return Q()
    if requested_language == "instrumental":
        return Q(isInstrumental=True) | ~Q(type=Track.TypeChoices.SONG)
    if requested_language == "hindi":
        return Q(language__iexact="hindi") | Q(genre__icontains="bollywood") | Q(region__iexact="india")
    return Q(language__iexact=requested_language)


def _style_query(music_style: str | None) -> Q:
    requested_style = _normalise(music_style)
    if not requested_style or requested_style == "no_preference":
        return Q()
    if requested_style == "bollywood":
        return Q(genre__icontains="bollywood") | Q(language__iexact="hindi") | Q(region__iexact="india")
    if requested_style == "hollywood":
        return Q(language__iexact="english") | Q(region__iexact="us")
    if requested_style == "classical":
        return Q(classicalForm__isnull=False) & ~Q(classicalForm="")
    if requested_style == "raga":
        return (Q(ragaName__isnull=False) & ~Q(ragaName="")) | Q(genre__icontains="raga")
    return Q(genre__iexact=requested_style) | Q(genre__icontains=requested_style)


def _type_query(music_preference: str | None) -> Q:
    if music_preference == "lyrics":
        return Q(type=Track.TypeChoices.SONG) | Q(isInstrumental=False)
    if music_preference == "no_lyrics":
        return Q(isInstrumental=True) | Q(type__in=[Track.TypeChoices.INSTRUMENTAL, Track.TypeChoices.AMBIENT])
    if music_preference == "background":
        return Q(type=Track.TypeChoices.AMBIENT) | Q(type=Track.TypeChoices.INSTRUMENTAL)
    return Q()


def _artist_query(preferred_artist: str | None) -> Q:
    artist_query = _normalise(preferred_artist)
    if not artist_query or artist_query in {"any", "none", "no_preference"}:
        return Q()

    parts = [part for part in artist_query.split("_") if len(part) > 1]
    query = Q(artistId__name__icontains=(preferred_artist or "").strip())
    for part in parts:
        query |= Q(artistId__name__icontains=part)
    return query


def _normalise(value: str | None) -> str:
    return (value or "").strip().lower().replace(" ", "_")


def _selection_reason(*, track: Track, mood_label: str, music_preference: str | None) -> str:
    if music_preference == "background" and track.type == Track.TypeChoices.AMBIENT:
        return PlaylistTrack.SelectionReason.TAG_MATCH
    if music_preference == "surprise":
        return PlaylistTrack.SelectionReason.NOVELTY
    if track.primaryMood == mood_label:
        return PlaylistTrack.SelectionReason.MOOD_MATCH
    return PlaylistTrack.SelectionReason.FALLBACK
