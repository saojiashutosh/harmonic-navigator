import csv
import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from tracks.models import Artist, Track

logger = logging.getLogger(__name__)

# Map energy+valence ranges to mood labels
MOOD_RULES = [
    # (energy_min, energy_max, valence_min, valence_max, mood_label)
    (0.75, 1.0, 0.70, 1.0, "celebratory"),
    (0.65, 1.0, 0.45, 1.0, "energized"),
    (0.00, 0.40, 0.00, 0.35, "melancholic"),
    (0.00, 0.35, 0.00, 0.40, "anxious"),
    (0.00, 0.45, 0.35, 1.0, "calm"),
    (0.30, 0.70, 0.30, 0.70, "focused"),
]


def infer_mood(energy: float, valence: float) -> str:
    for e_min, e_max, v_min, v_max, label in MOOD_RULES:
        if e_min <= energy <= e_max and v_min <= valence <= v_max:
            return label
    return "focused"


def infer_type(instrumentalness: float | None) -> str:
    if instrumentalness is not None and instrumentalness >= 0.6:
        return Track.TypeChoices.INSTRUMENTAL
    return Track.TypeChoices.SONG


def safe_float(value: str) -> float | None:
    try:
        v = float(value)
        return v if v == v else None  # NaN check
    except (ValueError, TypeError):
        return None


def safe_int(value: str) -> int | None:
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


class Command(BaseCommand):
    help = "Import tracks from the Kaggle Spotify CSV dataset into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default="/app/spotify_dataset.csv",
            help="Path to the CSV file.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Max number of tracks to import.",
        )
        parser.add_argument(
            "--genre",
            default=None,
            help="Only import tracks from this genre (e.g. 'pop', 'classical').",
        )

    def handle(self, *args, **options):
        path = options["path"]
        limit = options["limit"]
        genre_filter = options["genre"]

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if genre_filter:
            rows = [r for r in rows if r.get("track_genre", "").strip().lower() == genre_filter.lower()]

        if limit:
            rows = rows[:limit]

        if not rows:
            self.stdout.write("No rows to import.")
            return

        created = 0
        skipped = 0

        for row in rows:
            spotify_id = (row.get("track_id") or "").strip()
            if not spotify_id:
                skipped += 1
                continue

            if Track.objects.filter(spotifyId=spotify_id).exists():
                skipped += 1
                continue

            artist_name = (row.get("artists") or "").split(";")[0].strip()
            energy = safe_float(row.get("energy"))
            valence = safe_float(row.get("valence"))
            instrumentalness = safe_float(row.get("instrumentalness"))
            tempo = safe_int(row.get("tempo"))
            loudness = safe_float(row.get("loudness"))

            if energy is None or valence is None:
                skipped += 1
                continue

            artist = None
            if artist_name:
                artist, _ = Artist.objects.get_or_create(name=artist_name)

            with transaction.atomic():
                Track.objects.create(
                    title=(row.get("track_name") or "").strip() or None,
                    artistId=artist,
                    type=infer_type(instrumentalness),
                    source=Track.SourceChoices.SPOTIFY,
                    spotifyId=spotify_id,
                    externalUrl=f"https://open.spotify.com/track/{spotify_id}",
                    tempoBpm=tempo if tempo and 40 <= tempo <= 220 else None,
                    durationMs=safe_int(row.get("duration_ms")),
                    energy=energy,
                    valence=valence,
                    acousticness=safe_float(row.get("acousticness")),
                    instrumentalness=instrumentalness,
                    loudness=loudness if loudness and -60 <= loudness <= 0 else None,
                    primaryMood=infer_mood(energy, valence),
                    isInstrumental=infer_type(instrumentalness) == Track.TypeChoices.INSTRUMENTAL,
                    isExplicit=row.get("explicit", "").strip().lower() == "true",
                    isActive=True,
                    genre=(row.get("track_genre") or "").strip() or None,
                )
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Import complete — {created} tracks created, {skipped} skipped. Exporting to Excel..."
        ))

        from tracks.excel_storage import export_tracks_to_excel
        export_tracks_to_excel()

        self.stdout.write(self.style.SUCCESS(
            "Excel export complete."
        ))
