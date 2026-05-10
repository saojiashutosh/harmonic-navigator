from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from helpers.spotify_client import (
    SpotifyConfigurationError,
    SpotifyImportError,
    get_playlist_tracks,
)
from tracks.services import import_spotify_track


class Command(BaseCommand):
    help = "Import all tracks from a Spotify playlist into the catalog."

    def add_arguments(self, parser):
        parser.add_argument("url", help="Spotify playlist URL or ID.")
        parser.add_argument("--market", default=None, help="Spotify market code, e.g. IN or US.")
        parser.add_argument("--language", default=None, help="Language tag for all tracks, e.g. hindi.")
        parser.add_argument("--genre", default=None, help="Genre tag for all tracks, e.g. bollywood.")
        parser.add_argument("--region", default=None, help="Region tag for all tracks, e.g. india.")

    def handle(self, *args, **options):
        metadata = {
            k: options[k]
            for k in ("language", "genre", "region")
            if options[k] is not None
        }

        try:
            payloads = get_playlist_tracks(options["url"], market=options["market"])
        except SpotifyConfigurationError as exc:
            raise CommandError(str(exc)) from exc
        except SpotifyImportError as exc:
            raise CommandError(str(exc)) from exc

        if not payloads:
            self.stdout.write("No tracks found in playlist.")
            return

        self.stdout.write(f"Found {len(payloads)} tracks. Importing...")
        imported = 0
        skipped = 0

        for payload in payloads:
            try:
                track = import_spotify_track(payload, metadata=metadata)
                self.stdout.write(f"  + {track.title} — {track.artistId.name}")
                imported += 1
            except Exception as exc:
                self.stderr.write(f"  ! Failed: {payload.get('title')} — {exc}")
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(f"Done. Imported={imported} Skipped={skipped}")
        )
