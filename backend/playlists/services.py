from __future__ import annotations

import json
import random
import re
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q

from helpers.cache_utils import CANDIDATE_POOL_TTL, pool_cache_key

from feedback.models import TrackMoodScore, UserMoodPreference
from moods.constants import MUSIC_PREFERENCE_OVERRIDES
from moods.models import MoodInference, MoodSession
from tracks.models import Track, TrackMoodTag

from .constants import ARTIST_ERA, DEFAULT_PLAYLIST_SIZE, MOOD_TYPE_RATIOS, TARGET_TRACK_ATTRIBUTES
from .models import Playlist, PlaylistTrack


def build_playlist_for_session(
    session: MoodSession,
    *,
    limit: int = DEFAULT_PLAYLIST_SIZE,
) -> Playlist:
    inference, answer_map, chosen_tracks = _build_scored_tracklist(
        session, limit=limit
    )
    music_preference = answer_map.get("music_preference")

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


def expand_playlist(playlist: Playlist, *, extra: int) -> Playlist:
    """Append `extra` more tracks to an existing playlist.

    Requires the caller to have verified the user is authenticated.
    Tracks already in the playlist are excluded from the new batch.
    """
    session = playlist.moodInferenceId.moodSessionId

    existing_ids = frozenset(
        PlaylistTrack.objects.filter(playlistId=playlist)
        .values_list("trackId_id", flat=True)
    )
    current_count = playlist.trackCount or len(existing_ids)

    inference, answer_map, chosen_tracks = _build_scored_tracklist(
        session, limit=extra, exclude_ids=existing_ids
    )
    if not chosen_tracks:
        return playlist

    music_preference = answer_map.get("music_preference")

    with transaction.atomic():
        PlaylistTrack.objects.bulk_create(
            [
                PlaylistTrack(
                    playlistId=playlist,
                    trackId=track,
                    position=current_count + index,
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
        playlist.trackCount = current_count + len(chosen_tracks)
        playlist.save(update_fields=["trackCount"])

    return playlist


def _build_scored_tracklist(
    session: MoodSession,
    *,
    limit: int,
    exclude_ids: frozenset = frozenset(),
) -> tuple:
    """Score and select tracks for a session. Returns (inference, answer_map, [(track, score)]).

    Pure computation — does not write to the DB.
    Pass exclude_ids to omit tracks already in a playlist (used by expand_playlist).
    """
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
    era_preference = answer_map.get("music_era")
    time_of_day = answer_map.get("time_of_day")
    type_weights = _resolve_type_weights(
        user_id=session.userId_id,
        mood_label=inference.moodLabel,
        music_preference=music_preference,
    )

    # The questionnaire produces TWO signals:
    #  - inference.moodLabel   : how the user currently feels
    #  - playlist_goal         : what they want the music to DO for them
    #
    # When goal and current-mood diverge — e.g. the user feels melancholic
    # but asked to be uplifted — the goal must win, otherwise we serve sad
    # songs to someone explicitly asking for cheer. The earlier engine only
    # nudged scoring by +0.18 for "uplift" matches, which the hard mood
    # filter then overrode by locking the playlist into the inferred mood.
    #
    # Mapping: goal -> (primary playlist mood, optional broadening secondary).
    # "escape" intentionally keeps the inferred mood (escape INTO the
    # current feeling is a valid request).
    GOAL_MOOD_OVERRIDES = {
        "sleep":  ("calm",        None),
        "relax":  ("calm",        None),
        "focus":  ("focused",     None),
        "uplift": ("celebratory", "energized"),
        "party":  ("celebratory", "energized"),
    }

    inferred_secondary = getattr(inference, "secondaryMoodLabel", None)
    mood_blend_ratio = getattr(inference, "moodBlendRatio", 1.0) or 1.0

    if playlist_goal in GOAL_MOOD_OVERRIDES:
        playlist_mood, secondary_mood = GOAL_MOOD_OVERRIDES[playlist_goal]
        # When the override fires, the inferred mood blend no longer applies —
        # we're deliberately not mixing in tracks of the original mood.
        mood_blend_ratio = 0.85 if secondary_mood else 1.0
    elif inference.moodLabel == "anxious":
        # Anxious has no track pool of its own; ground the listener in calm.
        playlist_mood = "calm"
        secondary_mood = inferred_secondary
    else:
        playlist_mood = inference.moodLabel
        secondary_mood = inferred_secondary

    candidate_tracks = _build_candidate_pool(
        mood_label=playlist_mood,
        secondary_mood=secondary_mood,
        social_setting=social_setting,
        music_preference=music_preference,
        music_language=music_language,
        music_style=music_style,
        preferred_artist=preferred_artist,
        era_preference=era_preference,
        limit=limit,
    )
    if exclude_ids:
        candidate_tracks = [t for t in candidate_tracks if t.id not in exclude_ids]

    feedback_map = _feedback_score_map(
        user_id=session.userId_id,
        mood_label=inference.moodLabel,
        tracks=candidate_tracks,
    )
    # Pre-build a set of track IDs that have a matching mood tag for each mood —
    # avoids N+1 queries inside the scoring loop.
    mood_tag_ids = _mood_tag_track_ids(
        tracks=candidate_tracks,
        moods={playlist_mood, secondary_mood} - {None},
    )

    scored_tracks = []
    for track in candidate_tracks:
        relevance_score = _score_track(
            track=track,
            mood_label=playlist_mood,
            secondary_mood=secondary_mood,
            mood_blend_ratio=mood_blend_ratio,
            type_weights=type_weights,
            music_preference=music_preference,
            music_language=music_language,
            music_style=music_style,
            playlist_goal=playlist_goal,
            preferred_artist=preferred_artist,
            era_preference=era_preference,
            time_of_day=time_of_day,
            feedback_map=feedback_map,
            mood_tag_ids=mood_tag_ids,
        )
        scored_tracks.append((track, relevance_score))

    scored_tracks.sort(key=lambda item: item[1], reverse=True)

    # ── Hard language filter: never serve wrong-language tracks when language is set ──
    requested_languages = _parse_language_pref(music_language)
    if requested_languages:
        lang_matched = [
            (t, s) for t, s in scored_tracks
            if _track_matches_language(t, requested_languages)
        ]
        if lang_matched:
            scored_tracks = lang_matched
        else:
            scored_tracks = []

    # ── Hard mood filter: if enough mood-matched tracks exist, exclude others ──
    # A track is mood-matched when its primaryMood equals the playlist mood OR
    # it carries an explicit TrackMoodTag for that mood. Secondary-mood tracks
    # are included when a secondary mood is set, so the blend-diversity step
    # downstream still has material to work with.
    accepted_moods = {playlist_mood}
    if secondary_mood:
        accepted_moods.add(secondary_mood)
    accepted_tag_ids: set[str] = set()
    for m in accepted_moods:
        accepted_tag_ids |= mood_tag_ids.get(m, set())
    mood_matched = [
        (t, s) for t, s in scored_tracks
        if t.primaryMood in accepted_moods or str(t.id) in accepted_tag_ids
    ]
    if len(mood_matched) >= max(limit // 2, 3):
        scored_tracks = mood_matched

    # ── Hard era filter: when the user picks an era, that's a hard contract ──
    # Drop every track that doesn't match, even if the playlist ends up short.
    # The prior "only enforce if >= limit/2 matches" threshold meant sparse-era
    # buckets (e.g. very few "latest" Hindi focus tracks in the catalog)
    # silently fell back to wrong-era results, which defeats the whole point
    # of the era question.
    if era_preference and era_preference != "no_preference":
        scored_tracks = [
            (t, s) for t, s in scored_tracks
            if _track_matches_era(t, era_preference)
        ]

    # ── Deduplicate by base title (strip Remix/Lofi/From… variants) ───
    seen_base: set[str] = set()
    deduped: list = []
    for track, score in scored_tracks:
        bt = _base_title(track.title)
        if bt in seen_base:
            continue
        seen_base.add(bt)
        deduped.append((track, score))
    scored_tracks = deduped

    # ── Secondary mood diversity mixing ───────────────────────────────
    # NOTE: use playlist_mood (the effective mood after any goal override),
    # not inference.moodLabel. When a goal override fires (e.g. uplift
    # remaps melancholic -> celebratory), the pool no longer contains
    # tracks of the original inferred mood — referencing inference.moodLabel
    # here makes primary_set empty and collapses the playlist to a single
    # diversity-slot track.
    if secondary_mood and mood_blend_ratio < 1.0:
        diversity_slots = max(1, int(limit * (1 - mood_blend_ratio) * 0.4))
        secondary_tag_ids = mood_tag_ids.get(secondary_mood, set())
        primary_set = {
            t for t, _ in scored_tracks
            if t.primaryMood == playlist_mood
            or str(t.id) in mood_tag_ids.get(playlist_mood, set())
        }
        secondary_set = {
            t for t, _ in scored_tracks
            if (
                t.primaryMood == secondary_mood
                or str(t.id) in secondary_tag_ids
            ) and t not in primary_set
        }
        primary_tracks = [(t, s) for t, s in scored_tracks if t in primary_set]
        secondary_tracks = [(t, s) for t, s in scored_tracks if t in secondary_set]
        primary_take = primary_tracks[: limit - diversity_slots]
        secondary_take = secondary_tracks[:diversity_slots]
        chosen_tracks = primary_take + secondary_take
        chosen_tracks.sort(key=lambda item: item[1], reverse=True)
        chosen_tracks = chosen_tracks[:limit]
    else:
        chosen_tracks = scored_tracks[:limit]

    return inference, answer_map, chosen_tracks


def _build_candidate_pool(
    *,
    mood_label: str,
    secondary_mood: str | None = None,
    social_setting: str | None,
    music_preference: str | None,
    music_language: str | None,
    music_style: str | None,
    preferred_artist: str | None,
    era_preference: str | None = None,
    limit: int,
) -> list[Track]:
    key = pool_cache_key(
        mood_label=mood_label,
        secondary_mood=secondary_mood,
        social_setting=social_setting,
        music_language=music_language,
        music_style=music_style,
        music_preference=music_preference,
        preferred_artist=preferred_artist,
        era_preference=era_preference,
    )
    cached = cache.get(key)
    if cached is not None:
        # Reshuffle the cached pool so each session gets a different ordering
        # before scoring — the ±0.04 jitter alone isn't enough for full variety.
        random.shuffle(cached)
        return cached

    base_qs = Track.objects.select_related("artistId").filter(
        isActive=True,
    )
    if social_setting in {"kids", "meeting"}:
        base_qs = base_qs.filter(isExplicit=False)

    # Match mood via primaryMood field OR via TrackMoodTag relationship so
    # tracks with missing/incorrect primaryMood still surface when tagged.
    def _mood_q(label: str) -> Q:
        if not label:
            return Q()
        return Q(primaryMood=label) | Q(track_mood_tags__moodTagId__mood=label)

    mood_q = _mood_q(mood_label)
    secondary_mood_q = _mood_q(secondary_mood) if secondary_mood else Q()
    any_mood_q = mood_q | secondary_mood_q if secondary_mood else mood_q

    language_q = _language_query(music_language)
    style_q = _style_query(music_style)
    type_q = _type_query(music_preference)
    artist_q = _artist_query(preferred_artist)
    era_q = _era_query(era_preference)

    pool_size = max(limit * 25, 250)
    slice_size = max(limit * 8, 50)
    queries = [
        # 1. Perfect match: all filters + era
        artist_q & language_q & style_q & type_q & mood_q & era_q,
        # 2. Era + language + mood (no style)
        era_q & language_q & mood_q & type_q,
        # 3. Era + language (any mood) — pulls ALL era-correct language tracks
        #    into the pool before non-era tracks so scoring can rank them first
        era_q & language_q,
        # 4. Era + mood (any language)
        era_q & mood_q,
        # 5. Era only — maximise era-correct pool when era is requested
        era_q,
        # 6-7. Artist combos (artist preference overrides era)
        artist_q & language_q & type_q,
        artist_q & style_q & type_q,
        # 8-9. Language + style/mood combos (no era)
        language_q & style_q & type_q & mood_q,
        language_q & style_q & type_q,
        # 10-13. Partial combos prioritising language
        artist_q & any_mood_q,
        language_q & mood_q & type_q,
        language_q & any_mood_q,
        language_q & type_q,
        # 14. Language only
        language_q,
        # 15-17. Style / mood fallbacks
        style_q & mood_q & type_q,
        style_q & type_q,
        any_mood_q & type_q,
        # 18-21. Bare fallbacks
        artist_q,
        type_q,
        any_mood_q,
        Q(),
    ]

    selected: list[Track] = []
    seen_ids: set[str] = set()
    for query in queries:
        # Use distinct() because mood-tag JOINs can produce duplicate rows.
        queryset = base_qs if query == Q() else base_qs.filter(query).distinct()
        # Shuffle the batch so the candidate pool varies across sessions —
        # without this, DB insertion order always produces the same pool.
        track_batch = list(queryset[:slice_size])
        random.shuffle(track_batch)
        for track in track_batch:
            track_id = str(track.id)
            if track_id in seen_ids:
                continue
            seen_ids.add(track_id)
            selected.append(track)
            if len(selected) >= pool_size:
                cache.set(key, selected, CANDIDATE_POOL_TTL)
                return selected

    cache.set(key, selected, CANDIDATE_POOL_TTL)
    return selected


def _mood_tag_track_ids(
    *,
    tracks: list[Track],
    moods: set[str],
) -> dict[str, set[str]]:
    """Return {mood_label: {track_id_str, ...}} for all matching TrackMoodTag rows.

    Done in a single query to avoid N+1 inside the scoring loop.
    """
    if not tracks or not moods:
        return {}

    track_ids = [t.id for t in tracks]
    rows = TrackMoodTag.objects.filter(
        trackId_id__in=track_ids,
        moodTagId__mood__in=moods,
    ).values_list("trackId_id", "moodTagId__mood")

    result: dict[str, set[str]] = {m: set() for m in moods}
    for track_id, mood in rows:
        if mood in result:
            result[mood].add(str(track_id))
    return result


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
    secondary_mood: str | None = None,
    mood_blend_ratio: float = 1.0,
    type_weights: dict[str, float],
    music_preference: str | None,
    music_language: str | None,
    music_style: str | None,
    playlist_goal: str | None,
    preferred_artist: str | None,
    era_preference: str | None = None,
    time_of_day: str | None = None,
    feedback_map: dict[str, float],
    mood_tag_ids: dict[str, set[str]] | None = None,
) -> float:
    score = 0.0
    track_id_str = str(track.id)
    mood_tag_ids = mood_tag_ids or {}

    primary_tag_ids = mood_tag_ids.get(mood_label, set())
    secondary_tag_ids = mood_tag_ids.get(secondary_mood, set()) if secondary_mood else set()

    # ── Primary mood match (primaryMood field OR mood tag) ────────────
    if track.primaryMood == mood_label or track_id_str in primary_tag_ids:
        score += 0.50
    elif track.primaryMood:
        score += 0.04

    # ── Secondary mood bonus ──────────────────────────────────────────
    if secondary_mood and (
        track.primaryMood == secondary_mood or track_id_str in secondary_tag_ids
    ):
        secondary_bonus = 0.20 * (1.0 - mood_blend_ratio)
        score += secondary_bonus

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
        time_of_day=time_of_day,
    )

    score += _era_score(track=track, era_preference=era_preference)

    feedback_score = feedback_map.get(track_id_str)
    if feedback_score is not None:
        score += feedback_score * 0.20

    # Small random jitter breaks ties between tracks with nearly equal scores,
    # ensuring playlist variety across sessions with identical preferences.
    score += random.uniform(-0.04, 0.04)

    # Cap raised from 1.5 → 4.0: the real max score (mood + language + style +
    # era + lyrics) is ~2.3, so 1.5 was clipping everything and making all
    # qualifying tracks score identically, which killed sort differentiation.
    return round(min(max(score, 0.0), 4.0), 4)


def _taste_score(
    *,
    track: Track,
    music_language: str | None,
    music_style: str | None,
    playlist_goal: str | None,
    preferred_artist: str | None,
    time_of_day: str | None = None,
) -> float:
    score = 0.0
    language = _normalise(track.language)
    genre = _normalise(track.genre)
    region = _normalise(track.region)
    raga_name = _normalise(track.ragaName)
    classical_form = _normalise(track.classicalForm)
    artist_name = _normalise(getattr(track.artistId, "name", ""))

    requested_languages = _parse_language_pref(music_language)
    if requested_languages:
        matched_lang = False
        for lang in requested_languages:
            if lang == "instrumental" and track.isInstrumental:
                score += 0.50
                matched_lang = True
                break
            elif lang == language:
                score += 0.55
                matched_lang = True
                break
            elif lang == "hindi" and (genre == "bollywood" or genre == "desi" or region == "india"):
                score += 0.40
                matched_lang = True
                break
            elif lang == "marathi" and (genre == "marathi" or region == "maharashtra"):
                score += 0.40
                matched_lang = True
                break
        if not matched_lang:
            # Hard penalty: user explicitly requested a language — tracks that
            # don't match it should rank far below matching ones.
            score -= 0.55

    requested_style = _normalise(music_style)
    if requested_style and requested_style != "no_preference":
        if requested_style == genre:
            score += 0.40
        elif requested_style == "bollywood" and (language == "hindi" or genre == "bollywood" or region == "india"):
            score += 0.36
        elif requested_style == "hollywood" and (language == "english" or region in {"us", "uk"}):
            score += 0.30
        elif requested_style == "classical" and (classical_form or genre == "classical"):
            score += 0.34
        elif requested_style == "raga" and (raga_name or genre == "raga"):
            score += 0.36
        elif requested_style == "marathi" and (language == "marathi" or region == "maharashtra" or genre == "marathi"):
            score += 0.36
        elif requested_style == "instrumental" and (track.isInstrumental or track.type != Track.TypeChoices.SONG):
            score += 0.36
        elif requested_style == "lofi" and genre in {"lo-fi", "lofi", "chill", "ambient"}:
            score += 0.32
        elif requested_style == "indie" and genre in {"indie", "indie-pop", "alternative"}:
            score += 0.30
        elif requested_style == "pop" and genre in {"pop", "dance-pop", "synth-pop"}:
            score += 0.30
        elif requested_style == "devotional" and genre in {"devotional", "spiritual", "bhajan"}:
            score += 0.36
        else:
            # Explicit style mismatch penalty
            score -= 0.25

    requested_goal = _normalise(playlist_goal)
    if requested_goal == "focus" and track.primaryMood == "focused":
        score += 0.18
    elif requested_goal in {"relax", "sleep"} and track.primaryMood == "calm":
        score += 0.30
    elif requested_goal == "sleep" and track.energy is not None and track.energy > 0.55:
        score -= 0.30
    elif requested_goal == "uplift" and track.primaryMood in {"energized", "celebratory"}:
        score += 0.18
    elif requested_goal == "escape" and track.primaryMood in {"calm", "melancholic"}:
        score += 0.16
    elif requested_goal == "party" and track.primaryMood == "celebratory":
        score += 0.22

    tod = _normalise(time_of_day)
    if tod == "late_night":
        if track.primaryMood == "calm" or (track.energy is not None and track.energy <= 0.35):
            score += 0.14
        if track.energy is not None and track.energy > 0.65:
            score -= 0.20
    elif tod == "morning":
        if track.primaryMood in {"energized", "focused"}:
            score += 0.10

    artist_query = _normalise(preferred_artist)
    if artist_query and artist_query not in {"any", "none", "no_preference"}:
        if artist_query in artist_name:
            score += 0.75
        else:
            # Small penalty only — the artist preference is a bonus, not an
            # eliminator; other well-matched tracks should still appear.
            score -= 0.05

    if track.artistPopularity is not None:
        score += min(track.artistPopularity / 100, 1.0) * 0.05

    return score


_ARTIST_ERA_NORMALIZED = {
    re.sub(r"[\s\.\-_]+", "", name).lower(): era
    for name, era in ARTIST_ERA.items()
}


def _inferred_artist_era(track: Track) -> str | None:
    artist = getattr(track.artistId, "name", None) if track.artistId_id else None
    if not artist:
        return None
    direct = ARTIST_ERA.get(artist)
    if direct:
        return direct
    # Tolerant lookup so spelling variants (extra spaces, "Mehmood" vs
    # "Mahmood", "Laxmikant - Pyarelal" vs "Laxmikant-Pyarelal") still match.
    key = re.sub(r"[\s\.\-_]+", "", artist).lower()
    return _ARTIST_ERA_NORMALIZED.get(key)


def _era_score(*, track: Track, era_preference: str | None) -> float:
    if not era_preference or era_preference == "no_preference":
        return 0.0
    # Artist-era mapping wins over releaseYear. Spotify's release_year for
    # classic-artist tracks routinely reflects a remaster/compilation reissue
    # year (e.g. Kishore Kumar "Mere Naina Sawan Bhadon" returned as 2012),
    # which would otherwise make a 2010s-filtered playlist pull in 70s playback.
    inferred = _inferred_artist_era(track)
    if inferred:
        return 0.45 if inferred == era_preference else -0.70
    year = track.releaseYear
    if year is None:
        # No year and no inference — mild penalty so confirmed tracks win,
        # but not so harsh that the playlist collapses when many tracks have
        # missing years.
        return -0.20
    if era_preference == "latest" and year >= 2024:
        return 0.55
    if era_preference == "recent" and 2020 <= year <= 2023:
        return 0.52
    if era_preference == "era_2010s" and 2010 <= year <= 2019:
        return 0.48
    if era_preference == "era_2000s" and 2000 <= year <= 2009:
        return 0.48
    if era_preference == "nineties" and 1990 <= year < 2000:
        return 0.50
    # Wrong era — penalty must exceed the max positive mood score (+0.50) so
    # correct-era tracks always dominate regardless of mood match strength.
    return -0.70


def _track_matches_language(track: Track, requested_languages: list[str]) -> bool:
    language = _normalise(track.language)
    genre = _normalise(track.genre)
    region = _normalise(track.region)
    for lang in requested_languages:
        if lang == "instrumental" and track.isInstrumental:
            return True
        if lang == language:
            return True
        if lang == "hindi" and (genre in {"bollywood", "desi"} or region == "india"):
            return True
        if lang == "marathi" and (genre == "marathi" or region == "maharashtra"):
            return True
    return False


_REISSUE_TITLE_RE = re.compile(
    r"\b(remaster(?:ed)?|reissue|jhankar|lofi|lo[\s\-]?fi|slowed|reverb|"
    r"reprise|unplugged|revisited|recreated|cover|tribute|reimagined|"
    r"re[\s\-]?make|mashup|medley|soundtrack\s+version)\b",
    re.IGNORECASE,
)


def _track_matches_era(track: Track, era_preference: str | None) -> bool:
    if not era_preference or era_preference == "no_preference":
        return True
    # Artist mapping is authoritative when present (handles Spotify remaster
    # years for classic-era artists).
    inferred = _inferred_artist_era(track)
    if inferred:
        return inferred == era_preference
    # Remaster / reissue / cover titles can never be "latest" — the
    # releaseYear on those Spotify records is the reissue date, not the
    # original drop. Reject them outright when the user asked for latest.
    if era_preference == "latest" and _REISSUE_TITLE_RE.search(track.title or ""):
        return False
    year = track.releaseYear
    if year is None:
        return False
    if era_preference == "latest":
        return year >= 2024
    if era_preference == "recent":
        return 2020 <= year <= 2023
    if era_preference == "era_2010s":
        return 2010 <= year <= 2019
    if era_preference == "era_2000s":
        return 2000 <= year <= 2009
    if era_preference == "nineties":
        return 1990 <= year < 2000
    return True


def _era_query(era_preference: str | None) -> Q:
    if not era_preference or era_preference == "no_preference":
        return Q()
    # Artists in ARTIST_ERA: include if their era matches the request,
    # exclude otherwise — regardless of releaseYear. This keeps Kishore Kumar
    # / Lata Mangeshkar / etc. out of 2010s+ playlists even when Spotify
    # stamped their tracks with a remaster reissue year.
    matched_artists = [name for name, era in ARTIST_ERA.items() if era == era_preference]
    wrong_artists   = [name for name, era in ARTIST_ERA.items() if era != era_preference]
    matched_artist_q = Q(artistId__name__in=matched_artists) if matched_artists else Q(pk__in=[])
    wrong_artist_q   = Q(artistId__name__in=wrong_artists)   if wrong_artists   else Q(pk__in=[])

    if era_preference == "latest":
        year_q = Q(releaseYear__gte=2024)
    elif era_preference == "recent":
        year_q = Q(releaseYear__gte=2020, releaseYear__lte=2023)
    elif era_preference == "era_2010s":
        year_q = Q(releaseYear__gte=2010, releaseYear__lte=2019)
    elif era_preference == "era_2000s":
        year_q = Q(releaseYear__gte=2000, releaseYear__lte=2009)
    elif era_preference == "nineties":
        year_q = Q(releaseYear__gte=1990, releaseYear__lt=2000)
    else:
        return Q()

    # Match by artist OR (year match AND artist not mapped to a different era).
    return matched_artist_q | (year_q & ~wrong_artist_q)


def _parse_language_pref(raw_value: str | None) -> list[str]:
    """Parse music_language rawValue — plain string or JSON array — into a normalised list."""
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed, list):
            return [v.strip().lower() for v in parsed if v and v.strip().lower() != "no_preference"]
        val = str(parsed).strip().lower()
        return [val] if val and val != "no_preference" else []
    except (json.JSONDecodeError, TypeError):
        val = raw_value.strip().lower()
        return [val] if val and val != "no_preference" else []


def _language_query(music_language: str | None) -> Q:
    languages = _parse_language_pref(music_language)
    if not languages:
        return Q()
    combined = Q()
    for lang in languages:
        if lang == "instrumental":
            combined |= Q(isInstrumental=True) | ~Q(type=Track.TypeChoices.SONG)
        elif lang == "hindi":
            # Punjabi tracks are part of the Hindi music pool
            combined |= (
                Q(language__iexact="hindi") | Q(language__iexact="punjabi")
                | Q(genre__icontains="bollywood") | Q(genre__icontains="punjabi")
                | Q(region__iexact="india")
            )
        else:
            combined |= Q(language__iexact=lang)
    return combined


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
    if requested_style == "marathi":
        return Q(language__iexact="marathi") | Q(region__icontains="maharashtra") | Q(genre__icontains="marathi")
    if requested_style == "instrumental":
        return Q(isInstrumental=True) | Q(type__in=[Track.TypeChoices.INSTRUMENTAL, Track.TypeChoices.AMBIENT])
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


_PAREN_RE = re.compile(r'\s*[\(\[\{][^\)\]\}]*[\)\]\}]')
_SUFFIX_RE = re.compile(
    r'\s*[-–]\s*(remix|remaster(?:ed)?|live|acoustic|lo.?fi|reprise|version|cover|'
    r'edit|extended|radio\s+edit|instrumental|from\s+.+)$',
    flags=re.IGNORECASE,
)


def _base_title(title: str) -> str:
    """Strip parenthetical/suffix variants so (Remix) and (Lofi) don't both appear."""
    t = _PAREN_RE.sub('', title)
    t = _SUFFIX_RE.sub('', t)
    return t.strip().lower()


def _selection_reason(*, track: Track, mood_label: str, music_preference: str | None) -> str:
    if music_preference == "background" and track.type == Track.TypeChoices.AMBIENT:
        return PlaylistTrack.SelectionReason.TAG_MATCH
    if music_preference == "surprise":
        return PlaylistTrack.SelectionReason.NOVELTY
    if track.primaryMood == mood_label:
        return PlaylistTrack.SelectionReason.MOOD_MATCH
    return PlaylistTrack.SelectionReason.FALLBACK
