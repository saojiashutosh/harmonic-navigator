import uuid

import pandas as pd
from django.core.management.base import BaseCommand

from tracks.excel_storage import get_song_excel_backup_path
from tracks.models import Artist, Track


class Command(BaseCommand):
    help = "Import tracks from the song_storage.xlsx workbook into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=None,
            help="Path to the Excel workbook. Defaults to SONG_EXCEL_BACKUP_PATH.",
        )

    def handle(self, *args, **options):
        path = options["path"] or str(get_song_excel_backup_path())
        df = pd.read_excel(path, engine="openpyxl")

        if df.empty:
            self.stdout.write("No rows found in the workbook.")
            return

        created_count = 0
        updated_count = 0

        for _, row in df.iterrows():
            artist_name = row.get("artist_name") or None
            artist_spotify_id = row.get("artist_spotify_id") or None

            artist = None
            if artist_name or artist_spotify_id:
                if artist_spotify_id and str(artist_spotify_id).strip():
                    artist, _ = Artist.objects.get_or_create(
                        spotifyId=str(artist_spotify_id).strip(),
                        defaults={"name": artist_name},
                    )
                elif artist_name:
                    artist, _ = Artist.objects.get_or_create(
                        name=artist_name,
                        defaults={"spotifyId": None},
                    )

            spotify_id = _clean(row.get("spotify_id"))
            track_id = _clean(row.get("id"))

            defaults = {
                "title": _clean(row.get("title")),
                "artistId": artist,
                "type": _clean(row.get("type")) or "song",
                "source": _clean(row.get("source")) or "manual",
                "fmaId": _clean(row.get("fma_id")),
                "previewUrl": _clean(row.get("preview_url")),
                "externalUrl": _clean(row.get("external_url")),
                "tempoBpm": _int_or_none(row.get("tempo_bpm")),
                "durationMs": _int_or_none(row.get("duration_ms")),
                "keySignature": _clean(row.get("key_signature")),
                "energy": _float_or_none(row.get("energy")),
                "valence": _float_or_none(row.get("valence")),
                "acousticness": _float_or_none(row.get("acousticness")),
                "instrumentalness": _float_or_none(row.get("instrumentalness")),
                "loudness": _float_or_none(row.get("loudness")),
                "primaryMood": _clean(row.get("primary_mood")),
                "language": _clean(row.get("language")),
                "genre": _clean(row.get("genre")),
                "region": _clean(row.get("region")),
                "artistPopularity": _int_or_none(row.get("artist_popularity")),
                "ragaName": _clean(row.get("raga_name")),
                "classicalForm": _clean(row.get("classical_form")),
                "isInstrumental": bool(row.get("is_instrumental", False)),
                "isExplicit": bool(row.get("is_explicit", False)),
                "isActive": bool(row.get("is_active", True)),
            }

            if spotify_id:
                track, created = Track.objects.update_or_create(
                    spotifyId=spotify_id,
                    defaults=defaults,
                )
            elif track_id:
                try:
                    pk = uuid.UUID(str(track_id))
                except (ValueError, AttributeError):
                    pk = None

                if pk and Track.objects.filter(id=pk).exists():
                    Track.objects.filter(id=pk).update(**{
                        k: v for k, v in defaults.items() if v is not None
                    })
                    track = Track.objects.get(id=pk)
                    created = False
                else:
                    track = Track.objects.create(**defaults)
                    created = True
            else:
                track = Track.objects.create(**defaults)
                created = True

            if created:
                created_count += 1
                self.stdout.write(f"  Created: {track.title}")
            else:
                updated_count += 1
                self.stdout.write(f"  Updated: {track.title}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete — {created_count} created, {updated_count} updated."
            )
        )


def _clean(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value).strip() or None


def _int_or_none(value) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _float_or_none(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
