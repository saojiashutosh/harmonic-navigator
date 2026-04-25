from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from helpers.excel_storage import export_tracks_to_excel
from tracks.services import import_spotify_search_results
from helpers.spotify_client import SpotifyConfigurationError, SpotifyImportError


DEFAULT_QUERY_PACKS = [
    {"query": "bollywood", "language": "hindi", "genre": "bollywood", "region": "india"},
    {"query": "hindi lofi", "language": "hindi", "genre": "lofi", "region": "india"},
    {"query": "english pop", "language": "english", "genre": "pop", "region": "global"},
    {"query": "english indie", "language": "english", "genre": "indie", "region": "global"},
    {"query": "punjabi pop", "language": "punjabi", "genre": "pop", "region": "india"},
    {"query": "marathi hits", "language": "marathi", "genre": "pop", "region": "india"},
    {"query": "tamil hits", "language": "tamil", "genre": "pop", "region": "india"},
    {"query": "telugu hits", "language": "telugu", "genre": "pop", "region": "india"},
    {"query": "kannada hits", "language": "kannada", "genre": "pop", "region": "india"},
    {"query": "malayalam hits", "language": "malayalam", "genre": "pop", "region": "india"},
    {"query": "bengali hits", "language": "bengali", "genre": "pop", "region": "india"},
    {"query": "gujarati hits", "language": "gujarati", "genre": "pop", "region": "india"},
    {"query": "urdu ghazals", "language": "urdu", "genre": "ghazal", "region": "india"},
    {"query": "bhojpuri hits", "language": "bhojpuri", "genre": "pop", "region": "india"},
    {"query": "odia hits", "language": "odia", "genre": "pop", "region": "india"},
    {"query": "assamese hits", "language": "assamese", "genre": "pop", "region": "india"},
    {"query": "haryanvi hits", "language": "haryanvi", "genre": "pop", "region": "india"},
    {"query": "rajasthani hits", "language": "rajasthani", "genre": "pop", "region": "india"},
]


class Command(BaseCommand):
    help = "Import recent Spotify tracks from the last N years for the supported catalog tastes."

    def add_arguments(self, parser):
        parser.add_argument("--years", type=int, default=5, help="How many recent years to import, including the current year.")
        parser.add_argument("--per-query", type=int, default=10, help="How many Spotify tracks to import for each year/query pack.")
        parser.add_argument("--market", default=None, help="Spotify market code, e.g. IN or US.")

    def handle(self, *args, **options):
        years = max(options["years"], 1)
        per_query = max(options["per_query"], 1)
        current_year = datetime.utcnow().year
        year_values = list(range(current_year - years + 1, current_year + 1))

        imported_total = 0
        try:
            for year in year_values:
                for pack in DEFAULT_QUERY_PACKS:
                    query = f'{pack["query"]} year:{year}'
                    metadata = {
                        "language": pack["language"],
                        "genre": pack["genre"],
                        "region": pack["region"],
                    }
                    tracks = import_spotify_search_results(
                        query=query,
                        limit=per_query,
                        market=options["market"],
                        metadata=metadata,
                    )
                    imported_total += len(tracks)
                    self.stdout.write(f"Imported {len(tracks)} tracks for {query}")
        except SpotifyConfigurationError as exc:
            raise CommandError(str(exc)) from exc
        except SpotifyImportError as exc:
            raise CommandError(str(exc)) from exc

        export_tracks_to_excel()
        self.stdout.write(self.style.SUCCESS(f"Recent Spotify import finished. Imported {imported_total} tracks."))
