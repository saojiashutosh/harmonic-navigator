"""
Import tracks from a JSON file produced by fetch_playlist.py.

Usage:
    python manage.py import_from_json <path_to_json> --language hindi --genre bollywood
    python manage.py import_from_json /data/90s.json --language hindi --genre bollywood
"""
from __future__ import annotations

import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from tracks.models import Artist, Track


class Command(BaseCommand):
    help = "Import tracks from a fetch_playlist.py JSON dump."

    def add_arguments(self, parser):
        parser.add_argument("json_file", help="Path to the JSON file.")
        parser.add_argument("--language", default=None)
        parser.add_argument("--genre", default=None)
        parser.add_argument("--region", default=None)
        parser.add_argument("--primary-mood", dest="primaryMood", default=None)

    def handle(self, *args, **options):
        path = Path(options["json_file"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        with open(path, encoding="utf-8") as f:
            records = json.load(f)

        self.stdout.write(f"Found {len(records)} tracks in {path.name}")

        metadata = {k: v for k, v in {
            "language": options["language"],
            "genre": options["genre"],
            "region": options["region"],
            "primaryMood": options["primaryMood"],
        }.items() if v is not None}

        imported = skipped = 0

        for rec in records:
            spotify_id = rec.get("spotify_id")
            if not spotify_id:
                skipped += 1
                continue

            release_date = rec.get("release_date") or ""
            release_year = None
            if release_date:
                try:
                    release_year = int(release_date[:4])
                except ValueError:
                    pass

            try:
                with transaction.atomic():
                    artist_spotify_id = rec.get("artist_spotify_id")
                    artist_name = rec.get("artist_name") or "Unknown"

                    if artist_spotify_id:
                        artist, _ = Artist.objects.update_or_create(
                            spotifyId=artist_spotify_id,
                            defaults={"name": artist_name, "spotifyId": artist_spotify_id},
                        )
                    else:
                        artist = Artist.objects.filter(name=artist_name).first()
                        if not artist:
                            artist = Artist.objects.create(name=artist_name)

                    defaults = {
                        "title": rec.get("title", "Unknown"),
                        "artistId": artist,
                        "source": Track.SourceChoices.SPOTIFY,
                        "previewUrl": rec.get("preview_url"),
                        "externalUrl": rec.get("external_url"),
                        "durationMs": rec.get("duration_ms"),
                        "isExplicit": bool(rec.get("is_explicit", False)),
                        "isInstrumental": False,
                        "type": Track.TypeChoices.SONG,
                        "isActive": True,
                        "releaseYear": release_year,
                        "language": metadata.get("language"),
                        "genre": metadata.get("genre"),
                        "region": metadata.get("region"),
                        "primaryMood": metadata.get("primaryMood") or "focused",
                    }

                    track, created = Track.objects.update_or_create(
                        spotifyId=spotify_id,
                        defaults=defaults,
                    )

                    action = "+" if created else "~"
                    self.stdout.write(
                        f"  {action} {track.title} — {artist.name} ({release_year or '?'})"
                    )
                    imported += 1

            except Exception as exc:
                self.stderr.write(f"  ! Failed: {rec.get('title')} — {exc}")
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(f"Done. Imported/updated={imported}  Skipped={skipped}")
        )
