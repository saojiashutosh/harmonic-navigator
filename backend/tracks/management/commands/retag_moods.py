"""Re-derive primaryMood across the catalogue.

The original mood-inference rule (energy >= 0.75 & valence >= 0.70 -> celebratory,
otherwise progressively looser thresholds, with "focused" as the catch-all)
sent ~50% of all tracks into the "focused" bucket because most Bollywood,
Marathi and indie songs land in the moderate 0.45-0.65 energy / 0.40-0.60
valence band. The result: "celebratory" or "energized" mood requests get
flooded with "focused" tracks via the candidate-pool fallback queries.

This command re-derives primaryMood using three signals in order of
specificity:

1. Title-keyword overrides ("sad", "bewafa", "tanha" -> melancholic;
   "dance", "party", "naach" -> celebratory; devotional terms -> calm).
2. Genre-aware floors ("devotional", "bhajan", "lullaby" -> calm;
   "bhangra", "edm" + tempo >= 120 -> celebratory).
3. Loosened energy/valence thresholds with a final "focused" bucket
   that's now reserved for genuinely mid-tempo neutral-mood tracks.

Run: docker compose exec web python manage.py retag_moods
"""
from __future__ import annotations

import re
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from tracks.models import Track

# ── Title patterns (lowercased) ────────────────────────────────────────────
MELANCHOLIC_WORDS = re.compile(
    r"\b(sad|tanha|tanhai|bewafa|judaai|dard|udaas|alvida|bichd|adhoor|"
    r"akela|gum|gham|akele|toot|bhula|yaad|rona|gham|broken|lonely|tears|"
    r"misery|cry|alone|farewell|goodbye)\b",
    re.IGNORECASE,
)
CELEBRATORY_WORDS = re.compile(
    r"\b(naach|dance|party|jhoom|jhoome|dhoom|baraat|baaraat|sangeet|"
    r"masti|dhamaal|dhamaka|zingaat|wedding|celebrat|disco|jashn|raas|"
    r"rangrez|holi|garba|dandiya|bhangra|jingle)\b",
    re.IGNORECASE,
)
CALM_WORDS = re.compile(
    r"\b(lullaby|sleep|nidra|raat|chaand|sukoon|shanti|peace|meditation|"
    r"prayer|bhajan|aarti|mantra|stotra|stuti|kirtan|saregama)\b",
    re.IGNORECASE,
)

CELEBRATORY_GENRES = {"bhangra", "edm", "dance", "disco", "funk"}
CALM_GENRES = {"devotional", "spiritual", "bhajan", "lullaby", "ambient", "lo-fi", "lofi"}


def _g(value: str | None) -> str:
    return (value or "").strip().lower()


def derive_mood(track: Track) -> str:
    title = track.title or ""
    genre = _g(track.genre)
    energy = track.energy
    valence = track.valence
    tempo = track.tempoBpm

    # 1. Title-keyword overrides — these are unambiguous signals
    if MELANCHOLIC_WORDS.search(title):
        return "melancholic"
    if CELEBRATORY_WORDS.search(title):
        return "celebratory"
    if CALM_WORDS.search(title):
        return "calm"

    # 2. Genre floors
    if genre in CALM_GENRES:
        return "calm"
    if genre in CELEBRATORY_GENRES and tempo and tempo >= 115:
        return "celebratory"

    # 3. Feature-based, looser than the original thresholds
    if energy is not None and valence is not None:
        if energy >= 0.70 and valence >= 0.60:
            return "celebratory"
        if energy >= 0.60 and valence >= 0.45:
            return "energized"
        if energy <= 0.40 and valence <= 0.40:
            return "melancholic"
        if energy <= 0.55 and valence >= 0.30:
            return "calm"
        # Anything left in the moderate band falls through to focused
        return "focused"

    # 4. Missing features — derive from genre + tempo + language
    language = _g(track.language)
    if tempo:
        if tempo >= 125 and genre in {"bollywood", "marathi", "punjabi", "pop", "rock"}:
            return "celebratory"
        if tempo >= 110:
            return "energized"
        if tempo <= 75:
            return "calm"
    if genre in {"bollywood", "marathi", "pop", "rock"}:
        return "energized"  # Bollywood/pop defaults to energized rather than focused
    if language == "instrumental" or track.isInstrumental:
        return "focused"
    return "calm"


class Command(BaseCommand):
    help = "Re-derive primaryMood across all active tracks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the proposed distribution but do not write to the DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        qs = Track.objects.filter(isActive=True)
        total = qs.count()

        before = Counter(qs.values_list("primaryMood", flat=True))
        self.stdout.write(f"BEFORE — {total} active tracks:")
        for m, c in before.most_common():
            self.stdout.write(f"  {m or '<NULL>':14s} {c:5d}")

        changed = 0
        after: Counter = Counter()
        updates: list[Track] = []

        for track in qs.iterator(chunk_size=500):
            new_mood = derive_mood(track)
            after[new_mood] += 1
            if track.primaryMood != new_mood:
                track.primaryMood = new_mood
                updates.append(track)
                changed += 1

        self.stdout.write(f"\nAFTER  — {sum(after.values())} active tracks:")
        for m, c in after.most_common():
            self.stdout.write(f"  {m:14s} {c:5d}")

        self.stdout.write(f"\n{changed} tracks would be re-tagged.")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no DB writes."))
            return

        with transaction.atomic():
            Track.objects.bulk_update(updates, ["primaryMood"], batch_size=500)
        self.stdout.write(self.style.SUCCESS(f"Updated {changed} tracks."))
