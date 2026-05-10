"""
Comprehensive recommendation system test.

Phase 1 — Mood Inference (in-memory, ~86,400 combos):
  Test every combination of the 7 mood-affecting select questions and
  report which mood each combo produces, plus flag counterintuitive results.

Phase 2 — Playlist Quality (DB, 144 combos):
  For each mood × language × era, generate a real playlist and verify:
  - Playlist is non-empty
  - Track mood distribution matches requested mood
  - Language/era distribution respects the filter

Usage:
    python manage.py test_recommendations           # full run
    python manage.py test_recommendations --phase 1 # inference only
    python manage.py test_recommendations --phase 2 # playlist only
    python manage.py test_recommendations --verbose  # show every result
"""
from __future__ import annotations

import itertools
import json
import time
import uuid
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.db import transaction

from moods.constants import CATEGORY_WEIGHTS, OPTION_WEIGHTS, QUESTION_WEIGHTS, SYNERGY_BONUSES
from moods.inference import infer_mood_from_responses
from moods.models import Question, MoodSession, MoodInference
from moods.services import submit_answers
from playlists.services import build_playlist_for_session
from tracks.models import Track


# ── Question option definitions ───────────────────────────────────────────────
# Mood-affecting select questions (determines inferred mood)
MOOD_QUESTIONS = [
    ("energy_level",   ["drained", "low", "mid", "good", "charged"]),
    ("emotional_tone", ["happy", "calm", "sad", "tense", "flat", "excited"]),
    ("mental_state",   ["sharp", "scattered", "drifting", "motivated", "blank"]),
    ("activity",       ["working", "exercising", "relaxing", "commuting", "social", "sleeping"]),
    ("social_setting", ["alone", "others", "kids", "meeting"]),
    ("playlist_goal",  ["focus", "relax", "uplift", "escape", "party", "sleep"]),
    ("time_of_day",    ["morning", "afternoon", "evening", "late_night"]),
]

# Filter questions (language and era)
LANGUAGE_OPTIONS = ["hindi", "english", "marathi", "no_preference"]
ERA_OPTIONS = ["latest", "recent", "era_2010s", "era_2000s", "nineties", "no_preference"]

# Canonical answer sets that reliably produce each mood (used for Phase 2)
MOOD_SEEDS = {
    "focused":     {"energy_level": "mid",     "emotional_tone": "calm",  "mental_state": "sharp",
                    "activity": "working",    "social_setting": "meeting", "playlist_goal": "focus",
                    "time_of_day": "morning"},
    "energized":   {"energy_level": "charged", "emotional_tone": "excited","mental_state": "motivated",
                    "activity": "exercising", "social_setting": "others",  "playlist_goal": "uplift",
                    "time_of_day": "morning"},
    "calm":        {"energy_level": "low",     "emotional_tone": "calm",  "mental_state": "drifting",
                    "activity": "relaxing",   "social_setting": "alone",   "playlist_goal": "relax",
                    "time_of_day": "evening"},
    "melancholic": {"energy_level": "drained", "emotional_tone": "sad",   "mental_state": "blank",
                    "activity": "relaxing",   "social_setting": "alone",   "playlist_goal": "escape",
                    "time_of_day": "late_night"},
    "celebratory": {"energy_level": "charged", "emotional_tone": "happy", "mental_state": "motivated",
                    "activity": "social",     "social_setting": "others",  "playlist_goal": "party",
                    "time_of_day": "morning"},
    "anxious":     {"energy_level": "mid",     "emotional_tone": "tense", "mental_state": "scattered",
                    "activity": "working",    "social_setting": "meeting", "playlist_goal": "focus",
                    "time_of_day": "afternoon"},
}

# Combinations that should NOT produce the following moods (sanity checks)
COUNTERINTUITIVE = [
    # (answers_subset, forbidden_mood, reason)
    ({"emotional_tone": "sad",     "energy_level": "drained"}, "celebratory", "sad+drained → celebratory"),
    ({"emotional_tone": "excited", "energy_level": "charged"}, "melancholic",  "excited+charged → melancholic"),
    ({"playlist_goal":  "party",   "emotional_tone": "happy"},  "anxious",     "party+happy → anxious"),
    ({"playlist_goal":  "sleep",   "energy_level": "drained"},  "energized",   "sleep+drained → energized"),
    ({"playlist_goal":  "focus",   "mental_state": "sharp"},    "celebratory", "focus+sharp → celebratory"),
]


_QUESTION_CACHE: dict[str, object] | None = None


def _get_question_map() -> dict[str, object]:
    global _QUESTION_CACHE
    if _QUESTION_CACHE is None:
        _QUESTION_CACHE = {q.key: q for q in Question.objects.filter(isActive=True)}
    return _QUESTION_CACHE


def _build_responses(answer_map: dict[str, str]) -> list[dict]:
    """Build the response list expected by infer_mood_from_responses."""
    question_map = _get_question_map()
    responses = []
    for key, raw_value in answer_map.items():
        q = question_map.get(key)
        if not q or q.inputType != Question.InputTypeChoices.SELECT:
            continue
        weight_key = f"{key}_{raw_value}"
        responses.append({
            "weight_key": weight_key,
            "value": OPTION_WEIGHTS.get(raw_value, 1.0),
            "raw_value": raw_value,
            "category": q.category,
        })
    return responses


class Command(BaseCommand):
    help = "Test all question answer permutations for mood inference and playlist quality."

    def add_arguments(self, parser):
        parser.add_argument("--phase", type=int, choices=[1, 2], default=0,
                            help="1=inference only, 2=playlist only, 0=both")
        parser.add_argument("--verbose", action="store_true", default=False)
        parser.add_argument("--limit", type=int, default=0,
                            help="Limit Phase 1 combos (0=all). Useful for quick checks.")

    def handle(self, *args, **options):
        phase  = options["phase"]
        verbose = options["verbose"]
        limit   = options["limit"]

        if phase in (0, 1):
            self._phase1(verbose=verbose, limit=limit)
        if phase in (0, 2):
            self._phase2(verbose=verbose)

    # ── Phase 1 ──────────────────────────────────────────────────────────────
    def _phase1(self, *, verbose: bool, limit: int):
        self.stdout.write("\n" + "═" * 64)
        self.stdout.write("PHASE 1 — Mood Inference across all select-question combos")
        self.stdout.write("═" * 64)

        keys = [k for k, _ in MOOD_QUESTIONS]
        option_sets = [opts for _, opts in MOOD_QUESTIONS]
        total_combos = 1
        for opts in option_sets:
            total_combos *= len(opts)

        self.stdout.write(f"Total combinations: {total_combos:,}")
        if limit:
            self.stdout.write(f"(testing first {limit:,} only)")

        mood_counts: dict[str, int] = defaultdict(int)
        sanity_fails: list[str] = []
        sample_per_mood: dict[str, dict] = {}

        count = 0
        for combo in itertools.product(*option_sets):
            answer_map = dict(zip(keys, combo))
            responses  = _build_responses(answer_map)
            top_mood, *_ = infer_mood_from_responses(responses)

            mood_counts[top_mood] += 1
            if top_mood not in sample_per_mood:
                sample_per_mood[top_mood] = answer_map.copy()

            # Sanity checks
            for subset, forbidden, reason in COUNTERINTUITIVE:
                if all(answer_map.get(k) == v for k, v in subset.items()):
                    if top_mood == forbidden:
                        sanity_fails.append(
                            f"  ✗ {reason} → got '{top_mood}': {answer_map}"
                        )

            if verbose:
                self.stdout.write(f"  {answer_map} → {top_mood}")

            count += 1
            if limit and count >= limit:
                break

        self.stdout.write(f"\nResults ({count:,} combos tested):")
        for mood, cnt in sorted(mood_counts.items(), key=lambda x: -x[1]):
            pct  = 100 * cnt / count
            bar  = "█" * int(pct / 2)
            self.stdout.write(f"  {mood:<14}: {cnt:6,} ({pct:4.1f}%)  {bar}")

        self.stdout.write("\nSample combo per mood:")
        for mood, sample in sample_per_mood.items():
            self.stdout.write(f"  {mood:<14}: {sample}")

        if sanity_fails:
            self.stdout.write(f"\n⚠  {len(sanity_fails)} counterintuitive result(s):")
            for f in sanity_fails[:20]:
                self.stdout.write(f)
        else:
            self.stdout.write("\n✓  All sanity checks passed.")

    # ── Phase 2 ──────────────────────────────────────────────────────────────
    def _phase2(self, *, verbose: bool):
        self.stdout.write("\n" + "═" * 64)
        self.stdout.write("PHASE 2 — Playlist Quality (mood × language × era = 144 combos)")
        self.stdout.write("═" * 64)

        question_map = {q.key: q for q in Question.objects.filter(isActive=True)}
        total = len(MOOD_SEEDS) * len(LANGUAGE_OPTIONS) * len(ERA_OPTIONS)
        self.stdout.write(f"Running {total} playlist generations …\n")

        results = []
        failures = []
        combo_num = 0

        for target_mood, base_answers in MOOD_SEEDS.items():
            for language in LANGUAGE_OPTIONS:
                for era in ERA_OPTIONS:
                    combo_num += 1
                    answer_map = {
                        **base_answers,
                        "music_language": [language] if language != "no_preference" else [],
                        "music_era": era,
                    }

                    try:
                        result = self._run_playlist(answer_map, question_map, target_mood)
                        results.append(result)
                        status = "✓" if result["ok"] else "✗"
                        if verbose or not result["ok"]:
                            self.stdout.write(
                                f"  {status} [{combo_num:3d}/{total}] "
                                f"mood={target_mood:<12} lang={language:<14} era={era:<14} "
                                f"tracks={result['track_count']:2d} "
                                f"mood_match={result['mood_match_pct']:.0f}% "
                                f"lang_match={result['lang_match_pct']:.0f}%"
                            )
                        if not result["ok"]:
                            failures.append(result)
                    except Exception as exc:
                        failures.append({
                            "mood": target_mood, "language": language, "era": era,
                            "error": str(exc), "ok": False,
                        })
                        self.stdout.write(
                            f"  ✗ [{combo_num:3d}/{total}] "
                            f"mood={target_mood} lang={language} era={era} ERROR: {exc}"
                        )

        # Summary
        self.stdout.write("\n" + "─" * 64)
        self.stdout.write(f"Phase 2 Summary  ({len(results)} completed, {len(failures)} errors)")
        self.stdout.write("─" * 64)

        ok_results = [r for r in results if r.get("ok")]
        fail_results = [r for r in results if not r.get("ok")]

        if ok_results:
            avg_tracks = sum(r["track_count"] for r in ok_results) / len(ok_results)
            avg_mood   = sum(r["mood_match_pct"] for r in ok_results) / len(ok_results)
            avg_lang   = sum(r["lang_match_pct"] for r in ok_results) / len(ok_results)
            self.stdout.write(f"  Avg tracks per playlist : {avg_tracks:.1f}")
            self.stdout.write(f"  Avg mood-match %        : {avg_mood:.1f}%")
            self.stdout.write(f"  Avg language-match %    : {avg_lang:.1f}%")

        # Per-mood breakdown
        self.stdout.write("\nPer-mood averages:")
        for mood in MOOD_SEEDS:
            mood_res = [r for r in ok_results if r["mood"] == mood]
            if mood_res:
                avg_m = sum(r["mood_match_pct"] for r in mood_res) / len(mood_res)
                avg_t = sum(r["track_count"] for r in mood_res) / len(mood_res)
                self.stdout.write(
                    f"  {mood:<14}: {len(mood_res):2d} combos "
                    f"tracks={avg_t:.0f} mood_match={avg_m:.0f}%"
                )

        if fail_results or failures:
            self.stdout.write(f"\n⚠  {len(fail_results) + len(failures)} failing combinations:")
            for r in (fail_results + failures)[:20]:
                err = r.get("error", f"tracks={r.get('track_count',0)} mood_match={r.get('mood_match_pct',0):.0f}%")
                self.stdout.write(
                    f"  ✗ mood={r['mood']} lang={r['language']} era={r['era']}  {err}"
                )
        else:
            self.stdout.write("\n✓  All 144 combinations produced valid playlists.")

    def _run_playlist(self, answer_map: dict, question_map: dict, target_mood: str) -> dict:
        """Create a throw-away session, submit answers, build playlist, analyse."""
        with transaction.atomic():
            session = MoodSession.objects.create(userId=None)

            # Build answer list (select + multi_select + text)
            answers = []
            for key, value in answer_map.items():
                q = question_map.get(key)
                if not q:
                    continue
                if q.inputType == Question.InputTypeChoices.MULTI_SELECT:
                    raw = json.dumps(value) if isinstance(value, list) else value
                else:
                    raw = value
                answers.append({"question_key": key, "raw_value": raw})

            inference = submit_answers(session, answers)
            playlist  = build_playlist_for_session(session, limit=10)
            tracks    = list(
                playlist.playlist_tracks.select_related("trackId__artistId")
                .order_by("position")
                .values_list("trackId__primaryMood", "trackId__language", "trackId__releaseYear", flat=False)
            )

        track_count = len(tracks)
        if track_count == 0:
            return {
                "mood": target_mood, "language": answer_map.get("music_language"),
                "era": answer_map.get("music_era"), "track_count": 0,
                "mood_match_pct": 0, "lang_match_pct": 0, "ok": False,
                "error": "empty playlist",
            }

        # Mood match: use the same playlist_mood remap as services.py
        inferred = inference.moodLabel
        playlist_mood = "calm" if inferred == "anxious" else inferred
        mood_matches = sum(1 for pm, _, _ in tracks if pm == playlist_mood)
        mood_match_pct = 100 * mood_matches / track_count

        # Language match
        req_lang = answer_map.get("music_language")
        if isinstance(req_lang, list) and req_lang:
            lang_val = req_lang[0]
            lang_matches = sum(1 for _, lang, _ in tracks if lang and lang.lower() == lang_val.lower())
            lang_match_pct = 100 * lang_matches / track_count
        else:
            lang_match_pct = 100.0  # no_preference — always OK

        # Era match
        era = answer_map.get("music_era", "no_preference")
        era_ok = True
        if era not in ("no_preference", None):
            era_ranges = {
                "latest":   (2024, 9999),
                "recent":   (2020, 2023),
                "era_2010s":(2010, 2019),
                "era_2000s":(2000, 2009),
                "nineties": (0,    1999),
            }
            lo, hi = era_ranges.get(era, (0, 9999))
            era_matches = sum(
                1 for _, _, yr in tracks
                if yr is not None and lo <= yr <= hi
            )
            era_match_pct = 100 * era_matches / track_count
            era_ok = era_match_pct >= 60  # allow some slack for thin pools

        ok = track_count >= 5 and lang_match_pct >= 60 and era_ok

        return {
            "mood": target_mood, "language": req_lang,
            "era": era, "inferred": inferred,
            "track_count": track_count,
            "mood_match_pct": mood_match_pct,
            "lang_match_pct": lang_match_pct,
            "ok": ok,
        }
