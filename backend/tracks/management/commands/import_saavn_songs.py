"""
Import songs directly from JioSaavn search API.

Fetches real songs per language, keeping 50 per release year (1980-2025).
Songs imported here will always be playable since they come straight from JioSaavn.

Usage:
    python manage.py import_saavn_songs                    # all languages
    python manage.py import_saavn_songs --language hindi   # one language
    python manage.py import_saavn_songs --language hindi --start-year 2000 --end-year 2009
    python manage.py import_saavn_songs --per-year 50      # default target

The command is safe to re-run — it skips tracks already in the DB and
stops fetching a (year, language) bucket as soon as it is full.
"""
from __future__ import annotations

import hashlib
import time
import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from tracks.models import Artist, Track

# ── JioSaavn search queries ────────────────────────────────────────────────
# Each language gets several broad queries so we surface a wide variety of songs.
LANGUAGE_QUERIES: dict[str, list[str]] = {
    "hindi": [
        "bollywood hits", "hindi songs", "arijit singh", "dil pyaar",
        "romantic hindi", "hindi sad songs", "bollywood dance", "sufi hindi",
        "hindi old songs", "hindi classic", "kishore kumar", "lata mangeshkar",
        "sonu nigam", "shreya ghoshal", "ar rahman hindi", "pritam songs",
        "badshah hindi", "yo yo honey singh", "udit narayan", "kumar sanu",
        "hindi film songs", "hindi pop", "asha bhosle", "mohd rafi",
        # Era-targeted — 1980s
        "kishore kumar 1980", "lata mangeshkar 1980s", "asha bhosle 1983",
        "mohd rafi 1980", "hindi songs 1984", "hindi songs 1985",
        "hindi songs 1986", "hindi songs 1987", "hindi songs 1988",
        "bollywood 1980", "bollywood 1982", "bollywood 1984", "bollywood 1986",
        "ramesh sippy", "subhash ghai", "yash chopra songs",
        "rajesh roshan", "ravi shankar sharma", "bappi lahiri",
        # Era-targeted — 2001-2007
        "kabhi khushi kabhie gham", "lagaan songs", "devdas 2002",
        "kal ho na ho", "hum tum songs", "veer zaara", "bunty aur babli",
        "rang de basanti", "jab we met", "om shanti om", "dhoom songs",
        "black 2005", "parineeta songs", "salaam namaste", "krrish songs",
        "don 2006", "dhoom 2 songs", "guru 2007",
        # Gap fillers
        "hindi songs 2001", "hindi songs 2002", "hindi songs 2003",
        "hindi songs 2004", "hindi songs 2005", "hindi songs 2006",
        "hindi songs 2007", "hindi songs 2010", "hindi songs 2011",
        "hindi songs 2019", "hindi songs 2020",
        "shankar ehsaan loy", "vishal shekhar", "javed akhtar",
    ],
    "english": [
        "pop hits", "english songs", "love songs english", "rock hits",
        "ed sheeran", "taylor swift", "adele songs", "coldplay",
        "english sad songs", "dance pop", "r&b english", "indie pop",
        "billie eilish", "harry styles", "olivia rodrigo", "dua lipa",
        "the weeknd", "justin bieber", "ariana grande", "post malone",
        "english classic", "90s hits", "2000s hits", "80s songs",
    ],
    "marathi": [
        "marathi songs", "marathi hit", "ajay atul", "swapnil bandodkar",
        "marathi lavani", "marathi film songs", "marathi sad", "marathi dance",
        "avdhoot gupte", "hrishikesh ranade", "vaishali samant",
        "marathi devotional", "marathi romantic", "marathi classic",
        # Extra pass
        "marathi natya sangeet", "lata mangeshkar marathi", "asha bhosle marathi",
        "sudhir phadke", "manoj kumar marathi", "kishori amonkar",
        "pankaj udhas marathi", "adarsh shinde", "rohit raut marathi",
        "marathi songs 1990", "marathi songs 1995", "marathi songs 2000",
        "marathi songs 2005", "marathi songs 2010", "marathi natak songs",
        "marathi koligeet", "marathi lokgeet", "marathi bhaktigeet",
        "marathi songs 1985", "marathi 80s", "marathi 2000s hits",
        "bhalchandra pendharkar", "ram phutane", "anand shinde",
    ],
}

# Mood inference from title keywords (covers Hindi + English + regional)
_SAD_WORDS = {
    # English
    "sad", "farewell", "goodbye", "miss", "alone", "broken", "hurt",
    "pain", "cry", "tears", "sorry", "heartbreak", "love hurts",
    # Romanized Hindi / regional
    "dard", "tanha", "akela", "bichhad", "bichad", "judai", "rona",
    "ansoo", "aansoo", "pagal", "bewafa", "dhoka", "alvida", "intezaar",
    "tadap", "yaad", "rootha", "teri kami", "dil tuta", "rota", "toota",
    "bikhre", "gham", "judaai", "dil diya", "woh lamhe", "teri kasam",
    "kabhi alvida", "tujhse naraaz", "ek pyar ka nagma",
    # South Indian romanized
    "kadhal", "kaadhal", "prema", "pirivu", "virah",
}
_CALM_WORDS = {
    # English
    "acoustic", "peace", "rain", "slow", "gentle", "lullaby",
    "meditation", "prayer", "aarti",
    # Romanized Hindi
    "sufi", "ghazal", "sukoon", "shanti", "chaand", "chand", "raat",
    "subah", "neend", "nind", "aasmaan", "mehfil", "noor", "roshni",
    "sitaron", "chanda", "sohna", "pal", "aaina", "aa chal",
    "devotional", "bhajan", "kirtan", "amma", "maa", "qawwali",
    "raag", "raaga", "thumri", "dastan", "kahani", "khamoshi",
}
_ENERGY_WORDS = {
    # English
    "dance", "party", "remix", "dj", "beat", "pump", "fire", "rap",
    "hip hop", "rock", "metal", "bang", "swag", "scene",
    "bhangra", "dhol",
    # Romanized Hindi
    "naach", "nachle", "thumka", "dholki", "aaja", "balle", "hungama",
    "josh", "joshilay", "goli", "bullet", "power", "boom", "sher",
    "dabangg", "rowdy", "tezz", "bhaag", "nachna", "hulchul",
    "dhamaal", "dhamaka", "zor", "toofan", "aandhi",
}
_CELEBRATORY_WORDS = {
    # English
    "wedding", "happy", "celebration", "congratulations", "festival",
    "victory", "win", "holi", "diwali", "eid",
    # Romanized Hindi
    "shaadi", "baraat", "mehndi", "jashn", "khushi", "khushiyan",
    "yaar", "dost", "milke", "mubarak", "naya saal", "rang",
    "jeet", "fateh", "zindagi", "zindagi jee le", "jiyo",
    "masti", "mazaa", "toli", "sangat", "aayi hai bahaaren",
}

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


def _pseudo_energy_valence(track_id_str: str, mood: str) -> tuple[float, float]:
    """Derive deterministic energy/valence from JioSaavn ID + mood base."""
    h = int(hashlib.md5(track_id_str.encode()).hexdigest(), 16)
    base_e, base_v = _MOOD_BASE[mood]
    # Jitter ±0.12 around the mood baseline
    jitter_e = ((h & 0xFF) / 255.0 - 0.5) * 0.24
    jitter_v = (((h >> 8) & 0xFF) / 255.0 - 0.5) * 0.24
    energy  = min(1.0, max(0.05, base_e + jitter_e))
    valence = min(1.0, max(0.05, base_v + jitter_v))
    return round(energy, 3), round(valence, 3)


_SAAVN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.jiosaavn.com/",
}


def _saavn_search_page(query: str, page: int, results_per_page: int = 25) -> list[dict]:
    """Fetch one page from JioSaavn search.getResults. Returns list of song dicts."""
    try:
        r = requests.get(
            "https://www.jiosaavn.com/api.php",
            params={
                "__call": "search.getResults",
                "q": query,
                "p": page,
                "n": results_per_page,
                "q_format": "1",
                "_format": "json",
                "_marker": "0",
            },
            headers=_SAAVN_HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("results") or []
    except Exception:
        return []


def _parse_song(song: dict, fallback_language: str) -> dict | None:
    """Extract useful fields from a JioSaavn song result dict.

    JioSaavn search.getResults returns flat top-level fields — more_info is
    empty in this endpoint.  All artist/duration/language data is at root level.
    """
    title = (song.get("song") or song.get("title") or "").strip()
    if not title:
        return None

    # ── Artist: top-level primary_artists or singers (comma-separated strings)
    artist_name = (
        song.get("primary_artists") or
        song.get("singers") or
        song.get("music") or
        ""
    ).strip()
    # Take only the first artist if comma-separated ("Arijit Singh, Shreya Ghoshal")
    if "," in artist_name:
        artist_name = artist_name.split(",")[0].strip()
    if not artist_name:
        artist_name = "Unknown"

    # ── Year: top-level year or release_date
    year_raw = song.get("year") or song.get("release_date") or ""
    try:
        year = int(str(year_raw)[:4])
    except (ValueError, TypeError):
        year = None
    if year and not (1960 <= year <= 2026):
        year = None

    # ── Duration: top-level duration (seconds as int or string)
    dur = song.get("duration") or ""
    try:
        if ":" in str(dur):
            parts = str(dur).split(":")
            dur_ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
        else:
            dur_ms = int(float(dur)) * 1000
    except (ValueError, TypeError):
        dur_ms = None

    # ── Language: top-level language field
    lang = (song.get("language") or fallback_language).lower().strip()
    lang_map = {
        "hindi": "hindi", "english": "english", "marathi": "marathi",
        "punjabi": "punjabi", "tamil": "tamil", "telugu": "telugu",
        "kannada": "kannada", "malayalam": "malayalam", "bengali": "bengali",
        "urdu": "hindi",
    }
    lang = lang_map.get(lang, lang)

    # ── Explicit: "1" means explicit
    is_explicit = str(song.get("explicit_content") or "0") == "1"

    # ── Genre: infer from language (JioSaavn doesn't expose a genre field here)
    genre_map = {"hindi": "bollywood", "marathi": "marathi", "english": "pop"}
    genre = genre_map.get(lang)

    # ── JioSaavn internal ID
    saavn_id = str(song.get("id") or "")

    return {
        "title": title,
        "artist": artist_name,
        "language": lang,
        "year": year,
        "duration_ms": dur_ms,
        "is_explicit": is_explicit,
        "genre": genre,
        "saavn_id": saavn_id,
    }


class Command(BaseCommand):
    help = "Fetch songs from JioSaavn and import them, targeting 50 per year per language."

    def add_arguments(self, parser):
        parser.add_argument(
            "--language", "-l", type=str, default="all",
            help="Language to import (all / hindi / english / marathi / punjabi / tamil / telugu)",
        )
        parser.add_argument("--start-year", type=int, default=1980)
        parser.add_argument("--end-year",   type=int, default=2025)
        parser.add_argument(
            "--per-year", type=int, default=50,
            help="Target number of tracks per (language, year) bucket.",
        )
        parser.add_argument(
            "--max-pages", type=int, default=40,
            help="Max search-result pages to fetch per query (25 songs/page).",
        )
        parser.add_argument(
            "--delay", type=float, default=0.4,
            help="Seconds to sleep between API requests (be kind to JioSaavn).",
        )

    def handle(self, *args, **options):
        lang_arg   = options["language"].lower()
        start_year = options["start_year"]
        end_year   = options["end_year"]
        per_year   = options["per_year"]
        max_pages  = options["max_pages"]
        delay      = options["delay"]

        if lang_arg == "all":
            languages = list(LANGUAGE_QUERIES.keys())
        else:
            if lang_arg not in LANGUAGE_QUERIES:
                self.stderr.write(f"Unknown language '{lang_arg}'. "
                                  f"Choose from: {', '.join(LANGUAGE_QUERIES)}")
                return
            languages = [lang_arg]

        total_created = 0
        artist_cache: dict[str, Artist] = {}

        for language in languages:
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"Language: {language.upper()}  "
                              f"Years: {start_year}-{end_year}  Target: {per_year}/year")
            self.stdout.write(f"{'='*60}")

            # Track how many songs we have per year for this language
            year_counts: dict[int, int] = {}
            for y in range(start_year, end_year + 1):
                year_counts[y] = Track.objects.filter(
                    language=language, releaseYear=y
                ).count()

            full_years = {y for y, c in year_counts.items() if c >= per_year}
            if len(full_years) == (end_year - start_year + 1):
                self.stdout.write("  All year buckets already full — skipping.")
                continue

            created_lang = 0

            for query in LANGUAGE_QUERIES[language]:
                remaining = {y for y, c in year_counts.items()
                             if c < per_year and start_year <= y <= end_year}
                if not remaining:
                    self.stdout.write(f"  All buckets full after query '{query}' — done.")
                    break

                self.stdout.write(f"\n  Query: '{query}' "
                                  f"({len(remaining)} year-buckets still need songs)")

                for page in range(1, max_pages + 1):
                    songs_raw = _saavn_search_page(query, page)
                    time.sleep(delay)

                    if not songs_raw:
                        break  # no more results

                    for raw in songs_raw:
                        parsed = _parse_song(raw, language)
                        if not parsed:
                            continue
                        if parsed["language"] != language:
                            continue
                        year = parsed["year"]
                        if not year or not (start_year <= year <= end_year):
                            continue
                        if year_counts.get(year, 0) >= per_year:
                            continue

                        title       = parsed["title"]
                        artist_name = parsed["artist"]
                        saavn_id    = parsed["saavn_id"]

                        # Dedup by title + artist (exact match)
                        if Track.objects.filter(
                            title__iexact=title,
                            artistId__name__iexact=artist_name,
                        ).exists():
                            continue
                        # Also skip if base title (strip parens) already exists for same artist
                        base = title.split('(')[0].split('[')[0].strip()
                        if base and base.lower() != title.lower() and Track.objects.filter(
                            title__iexact=base,
                            artistId__name__iexact=artist_name,
                        ).exists():
                            continue

                        # Artist — use filter().first() to avoid MultipleObjectsReturned
                        # when duplicate artist names exist (no unique constraint on Artist.name)
                        ak = artist_name.lower()
                        if ak not in artist_cache:
                            artist = Artist.objects.filter(name=artist_name).first()
                            if artist is None:
                                artist = Artist.objects.create(name=artist_name)
                            artist_cache[ak] = artist
                        artist_obj = artist_cache[ak]

                        mood    = _infer_mood_from_title(title)
                        energy, valence = _pseudo_energy_valence(saavn_id or title, mood)

                        with transaction.atomic():
                            Track.objects.create(
                                title=title,
                                artistId=artist_obj,
                                type=Track.TypeChoices.SONG,
                                source=Track.SourceChoices.MANUAL,
                                language=language,
                                releaseYear=year,
                                durationMs=parsed["duration_ms"],
                                energy=energy,
                                valence=valence,
                                acousticness=round(0.3 + ((energy - 0.3) * -0.5), 3),
                                primaryMood=mood,
                                genre=parsed.get("genre"),
                                isInstrumental=False,
                                isExplicit=parsed.get("is_explicit", False),
                                isActive=True,
                            )

                        year_counts[year] = year_counts.get(year, 0) + 1
                        created_lang += 1
                        total_created += 1

                    # Check if all buckets are full after this page
                    remaining = {y for y, c in year_counts.items()
                                 if c < per_year and start_year <= y <= end_year}
                    if not remaining:
                        break

                # Brief pause between queries
                time.sleep(delay * 2)

            self.stdout.write(f"\n  Created {created_lang} tracks for {language}.")
            # Summary for this language
            filled = sum(1 for y in range(start_year, end_year + 1)
                         if year_counts.get(y, 0) >= per_year)
            self.stdout.write(
                f"  Year buckets filled: {filled}/{end_year - start_year + 1}"
            )

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Total created: {total_created} tracks")
        self.stdout.write("\nFinal DB summary:")
        for lang in LANGUAGE_QUERIES:
            c = Track.objects.filter(language=lang).count()
            self.stdout.write(f"  {lang:12s}: {c} tracks")
