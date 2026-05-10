"""
Reassign primaryMood (and matching energy/valence) for tracks that were
imported with the default "focused" label because their title contained no
recognisable English mood keyword.

Strategy per track:
  1. Re-run _infer_mood_from_title() with the extended Hindi keyword sets.
  2. If the result is still "focused" (no keyword hit), use a deterministic
     hash of the track UUID to redistribute into mood buckets that reflect
     real Bollywood proportions:
       calm 33%, melancholic 28%, energized 18%, celebratory 14%, focused 7%
  3. Assign energy/valence/acousticness using _pseudo_energy_valence() so
     the numeric features are consistent with the new mood label.

Usage:
    python manage.py reassign_track_moods
    python manage.py reassign_track_moods --language hindi --only-focused
    python manage.py reassign_track_moods --dry-run
"""
from __future__ import annotations

import hashlib
from django.core.management.base import BaseCommand
from django.db.models import Q
from tracks.models import Track

# ── Mood keyword sets (keep in sync with import_saavn_songs.py) ─────────────
_SAD_WORDS = {
    "sad", "farewell", "goodbye", "miss", "alone", "broken", "hurt",
    "pain", "cry", "tears", "sorry", "heartbreak", "love hurts",
    "dard", "tanha", "akela", "bichhad", "bichad", "judai", "rona",
    "ansoo", "aansoo", "pagal", "bewafa", "dhoka", "alvida", "intezaar",
    "tadap", "yaad", "rootha", "teri kami", "dil tuta", "rota", "toota",
    "bikhre", "gham", "judaai", "dil diya", "woh lamhe", "teri kasam",
    "kabhi alvida", "tujhse naraaz", "ek pyar ka nagma",
    "kadhal", "kaadhal", "prema", "pirivu", "virah",
}
_CALM_WORDS = {
    "acoustic", "peace", "rain", "slow", "gentle", "lullaby",
    "meditation", "prayer", "aarti",
    "sufi", "ghazal", "sukoon", "shanti", "chaand", "chand", "raat",
    "subah", "neend", "nind", "aasmaan", "mehfil", "noor", "roshni",
    "sitaron", "chanda", "sohna", "pal", "aaina", "aa chal",
    "devotional", "bhajan", "kirtan", "amma", "maa", "qawwali",
    "raag", "raaga", "thumri", "dastan", "kahani", "khamoshi",
}
_ENERGY_WORDS = {
    "dance", "party", "remix", "dj", "beat", "pump", "fire", "rap",
    "hip hop", "rock", "metal", "bang", "swag", "scene",
    "bhangra", "dhol",
    "naach", "nachle", "thumka", "dholki", "aaja", "balle", "hungama",
    "josh", "joshilay", "goli", "bullet", "power", "boom", "sher",
    "dabangg", "rowdy", "tezz", "bhaag", "nachna", "hulchul",
    "dhamaal", "dhamaka", "zor", "toofan", "aandhi",
}
_CELEBRATORY_WORDS = {
    "wedding", "happy", "celebration", "congratulations", "festival",
    "victory", "win", "holi", "diwali", "eid",
    "shaadi", "baraat", "mehndi", "jashn", "khushi", "khushiyan",
    "yaar", "dost", "milke", "mubarak", "naya saal", "rang",
    "jeet", "fateh", "zindagi", "zindagi jee le", "jiyo",
    "masti", "mazaa", "toli", "sangat", "aayi hai bahaaren",
}

# Redistribution buckets for tracks that still default to "focused"
# Cumulative thresholds (hash % 100 < threshold → mood)
_REDISTRIB_THRESHOLDS = [
    (33,  "calm"),
    (61,  "melancholic"),   # 33+28
    (79,  "energized"),     # 61+18
    (93,  "celebratory"),   # 79+14
    (100, "focused"),       # 93+7
]

# Energy / valence baselines per mood (same as import_saavn_songs._MOOD_BASE)
_MOOD_BASE = {
    "melancholic": (0.35, 0.25),
    "calm":        (0.40, 0.52),
    "focused":     (0.55, 0.52),
    "energized":   (0.73, 0.65),
    "celebratory": (0.82, 0.78),
}


def _infer_mood_from_title(title: str) -> str:
    t = title.lower()
    if any(w in t for w in _CELEBRATORY_WORDS):
        return "celebratory"
    if any(w in t for w in _ENERGY_WORDS):
        return "energized"
    if any(w in t for w in _SAD_WORDS):
        return "melancholic"
    if any(w in t for w in _CALM_WORDS):
        return "calm"
    return "focused"


def _redistribute_mood(track_id_str: str) -> str:
    h = int(hashlib.md5(track_id_str.encode()).hexdigest(), 16) % 100
    for threshold, mood in _REDISTRIB_THRESHOLDS:
        if h < threshold:
            return mood
    return "focused"


def _pseudo_energy_valence(track_id_str: str, mood: str) -> tuple[float, float]:
    h = int(hashlib.md5(track_id_str.encode()).hexdigest(), 16)
    base_e, base_v = _MOOD_BASE.get(mood, _MOOD_BASE["focused"])
    jitter_e = ((h & 0xFF) / 255.0 - 0.5) * 0.24
    jitter_v = (((h >> 8) & 0xFF) / 255.0 - 0.5) * 0.24
    energy  = min(1.0, max(0.05, base_e + jitter_e))
    valence = min(1.0, max(0.05, base_v + jitter_v))
    return round(energy, 3), round(valence, 3)


class Command(BaseCommand):
    help = "Reassign primaryMood for tracks defaulted to 'focused' by title inference."

    def add_arguments(self, parser):
        parser.add_argument("--language", "-l", type=str, default="all")
        parser.add_argument(
            "--only-focused", action="store_true", default=False,
            help="Only process tracks currently tagged primaryMood='focused'.",
        )
        parser.add_argument(
            "--dry-run", action="store_true", default=False,
            help="Show what would change without writing to DB.",
        )
        parser.add_argument("--batch", type=int, default=500)

    def handle(self, *args, **options):
        lang_arg   = options["language"]
        only_foc   = options["only_focused"]
        dry_run    = options["dry_run"]
        batch_size = options["batch"]

        qs = Track.objects.filter(isActive=True)
        if lang_arg != "all":
            qs = qs.filter(language__iexact=lang_arg)
        if only_foc:
            qs = qs.filter(Q(primaryMood="focused") | Q(primaryMood__isnull=True))

        total = qs.count()
        self.stdout.write(f"Processing {total} tracks (dry_run={dry_run}) …")

        changed = 0
        unchanged = 0
        mood_counts: dict[str, int] = {}

        to_update = []
        for track in qs.iterator(chunk_size=batch_size):
            new_mood = _infer_mood_from_title(track.title)
            if new_mood == "focused":
                new_mood = _redistribute_mood(str(track.id))

            mood_counts[new_mood] = mood_counts.get(new_mood, 0) + 1

            if new_mood == track.primaryMood:
                unchanged += 1
                continue

            energy, valence = _pseudo_energy_valence(str(track.id), new_mood)
            track.primaryMood  = new_mood
            track.energy       = energy
            track.valence      = valence
            track.acousticness = round(0.3 + ((energy - 0.3) * -0.5), 3)
            to_update.append(track)
            changed += 1

            if not dry_run and len(to_update) >= batch_size:
                Track.objects.bulk_update(
                    to_update, ["primaryMood", "energy", "valence", "acousticness"]
                )
                self.stdout.write(f"  … saved batch of {len(to_update)}")
                to_update = []

        if not dry_run and to_update:
            Track.objects.bulk_update(
                to_update, ["primaryMood", "energy", "valence", "acousticness"]
            )

        self.stdout.write(f"\nDone. changed={changed} unchanged={unchanged}")
        self.stdout.write("\nNew mood distribution:")
        for mood, count in sorted(mood_counts.items(), key=lambda x: -x[1]):
            pct = 100 * count / total if total else 0
            self.stdout.write(f"  {mood:<14}: {count:4d} ({pct:.0f}%)")
