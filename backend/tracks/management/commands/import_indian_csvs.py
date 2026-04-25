import csv
from pathlib import Path
import logging
import glob

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from tracks.models import Artist, Track

logger = logging.getLogger(__name__)

MOOD_RULES = [
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

def safe_float(value: str) -> float | None:
    try:
        v = float(value)
        return v if v == v else None
    except (ValueError, TypeError):
        return None

def parse_duration(value: str) -> int | None:
    try:
        parts = value.split(':')
        if len(parts) == 2:
            return (int(parts[0]) * 60 + int(parts[1])) * 1000
    except:
        pass
    return None

class Command(BaseCommand):
    help = "Bulk import Indian language tracks from CSVs dropped by user."

    def handle(self, *args, **options):
        dataset_dir = Path(settings.BASE_DIR) / "data"
        csv_files = glob.glob(str(dataset_dir / "*_songs.csv"))

        if not csv_files:
            self.stdout.write(f"No files ending with '_songs.csv' found in {dataset_dir}.")
            return

        created = 0
        skipped = 0

        for path in csv_files:
            self.stdout.write(f"Processing {Path(path).name}...")
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    title = row.get("song_name", "").strip()
                    artist_str = row.get("singer", "")
                    artist_name = artist_str.split("|")[0].strip() if artist_str else ""
                    
                    if not title or not artist_name:
                        skipped += 1
                        continue

                    # Prevent duplicate imports exactly
                    if Track.objects.filter(title__iexact=title, artistId__name__iexact=artist_name).exists():
                        skipped += 1
                        continue

                    energy = safe_float(row.get("energy"))
                    valence = safe_float(row.get("Valence"))
                    if energy is None or valence is None:
                        skipped += 1
                        continue

                    duration = parse_duration(row.get("duration", ""))
                    tempo = safe_float(row.get("tempo"))
                    tempo_int = int(tempo) if tempo else None
                    loudness = safe_float(row.get("loudness"))
                    acousticness = safe_float(row.get("acousticness"))
                    language = row.get("language", "").strip() or None

                    artist = Artist.objects.filter(name=artist_name).first()
                    if not artist:
                        artist = Artist.objects.create(name=artist_name)

                    with transaction.atomic():
                        Track.objects.create(
                            title=title,
                            artistId=artist,
                            type=Track.TypeChoices.SONG,
                            source=Track.SourceChoices.MANUAL,
                            durationMs=duration,
                            tempoBpm=tempo_int if tempo_int and 40 <= tempo_int <= 220 else None,
                            energy=energy,
                            valence=valence,
                            acousticness=acousticness,
                            loudness=loudness if loudness and -60 <= loudness <= 0 else None,
                            primaryMood=infer_mood(energy, valence),
                            isInstrumental=False,
                            isExplicit=False,
                            isActive=True,
                            language=language,
                        )
                        created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Import complete - {created} tracks created, {skipped} duplicates skipped. Saving to Excel..."
        ))
        
        from helpers.excel_storage import export_tracks_to_excel
        export_tracks_to_excel()

        self.stdout.write(self.style.SUCCESS("All synchronized to Excel successfully!"))
