from django.core.management.base import BaseCommand, CommandError

from tracks.services import import_spotify_search_results
from tracks.spotify_client import SpotifyConfigurationError, SpotifyImportError


class Command(BaseCommand):
    help = "Search Spotify and import matching tracks into the local catalog."

    def add_arguments(self, parser):
        parser.add_argument("--query", required=True, help="Search phrase to send to Spotify.")
        parser.add_argument("--limit", type=int, default=20, help="Maximum number of tracks to import.")
        parser.add_argument("--market", default=None, help="Optional Spotify market code, e.g. IN or US.")
        parser.add_argument("--language", default=None, help="Optional track language tag, e.g. hindi or english.")
        parser.add_argument("--genre", default=None, help="Optional genre/style tag, e.g. bollywood or lofi.")
        parser.add_argument("--region", default=None, help="Optional region tag, e.g. india or global.")
        parser.add_argument("--raga-name", dest="ragaName", default=None, help="Optional raga name.")
        parser.add_argument("--classical-form", dest="classicalForm", default=None, help="Optional classical form.")
        parser.add_argument("--artist-popularity", dest="artistPopularity", type=int, default=None, help="Optional 0-100 artist popularity score.")

    def handle(self, *args, **options):
        try:
            tracks = import_spotify_search_results(
                query=options["query"],
                limit=options["limit"],
                market=options["market"],
                metadata={
                    key: options.get(key)
                    for key in (
                        "language",
                        "genre",
                        "region",
                        "ragaName",
                        "classicalForm",
                        "artistPopularity",
                    )
                    if options.get(key) is not None
                },
            )
        except SpotifyConfigurationError as exc:
            raise CommandError(str(exc)) from exc
        except SpotifyImportError as exc:
            raise CommandError(str(exc)) from exc

        if not tracks:
            self.stdout.write("No tracks imported.")
            return

        for track in tracks:
            self.stdout.write(
                f"Imported {track.title} [{track.primaryMood}] -> {track.externalUrl or 'no external URL'}"
            )
        self.stdout.write(self.style.SUCCESS(f"Imported {len(tracks)} tracks."))
