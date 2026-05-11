from __future__ import annotations

import json
import time

from django.core.management.base import BaseCommand

from tracks.models import Track


def _extract_year(item: dict) -> int | None:
    album = item.get("album") or {}
    release_date = album.get("release_date") or item.get("release_date") or ""
    if release_date:
        try:
            return int(str(release_date)[:4])
        except (ValueError, TypeError):
            pass
    return None


class Command(BaseCommand):
    help = "Backfill releaseYear for tracks with a spotifyId but no releaseYear."

    def add_arguments(self, parser):
        parser.add_argument(
            "--delay",
            type=float,
            default=0.2,
            help="Seconds to sleep between API calls (default: 0.2).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max tracks to process in this run (0 = all).",
        )
        parser.add_argument(
            "--json-file",
            type=str,
            default="",
            help="Path to a JSON file mapping spotifyId -> releaseYear (skips API calls).",
        )

    def handle(self, *args, **options):
        delay = options["delay"]
        limit = options["limit"]
        json_file = options["json_file"]

        # ── Mode 1: apply from a pre-built JSON mapping ──────────────────────
        if json_file:
            self._apply_from_json(json_file)
            return

        # ── Mode 2: fetch via official Spotify API one-by-one ────────────────
        qs = (
            Track.objects
            .filter(releaseYear__isnull=True)
            .exclude(spotifyId__isnull=True)
            .exclude(spotifyId="")
        )
        total = qs.count()
        self.stdout.write(f"Tracks with NULL releaseYear: {total}")

        if limit:
            qs = qs[:limit]
            self.stdout.write(f"Processing first {limit} tracks.")

        try:
            from spotipy import Spotify
            from spotipy.oauth2 import SpotifyClientCredentials
            import os
            client_id = os.getenv("SPOTIFY_CLIENT_ID")
            client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
            if not client_id or not client_secret:
                raise RuntimeError("SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET not set.")
            client = Spotify(
                auth_manager=SpotifyClientCredentials(
                    client_id=client_id,
                    client_secret=client_secret,
                ),
                requests_timeout=10,
                retries=3,
            )
            self.stdout.write("Spotify client ready.")
        except Exception as exc:
            self.stderr.write(f"Cannot build Spotify client: {exc}")
            return

        updated = 0
        errors = 0

        for track in qs.iterator(chunk_size=100):
            try:
                from spotipy.exceptions import SpotifyException
                item = client.track(track.spotifyId)
                year = _extract_year(item)
                if year is not None:
                    track.releaseYear = year
                    track.save(update_fields=["releaseYear"])
                    updated += 1
                    if updated % 50 == 0:
                        self.stdout.write(f"  Updated {updated} tracks so far...")
                else:
                    errors += 1
            except Exception as exc:
                errors += 1
                if errors <= 10:
                    self.stderr.write(f"  Error on {track.spotifyId}: {exc}")

            time.sleep(delay)

        still_null = (
            Track.objects
            .filter(releaseYear__isnull=True)
            .exclude(spotifyId__isnull=True)
            .exclude(spotifyId="")
            .count()
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Updated={updated}  Errors={errors}  Still-null={still_null}"
            )
        )

    def _apply_from_json(self, path: str) -> None:
        with open(path) as f:
            mapping: dict = json.load(f)

        self.stdout.write(f"Loaded {len(mapping)} entries from {path}")
        updated = 0
        for spotify_id, year in mapping.items():
            if year is None:
                continue
            rows = Track.objects.filter(spotifyId=spotify_id, releaseYear__isnull=True)
            count = rows.update(releaseYear=int(year))
            updated += count

        still_null = (
            Track.objects
            .filter(releaseYear__isnull=True)
            .exclude(spotifyId__isnull=True)
            .exclude(spotifyId="")
            .count()
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Updated={updated}  Still-null={still_null}"
            )
        )
