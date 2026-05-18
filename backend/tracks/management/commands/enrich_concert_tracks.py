"""Backfill recommendation fields on concert-imported tracks.

Concert tracks fetched from JioSaavn (via ``_import_saavn_track``) were
historically created with only basic metadata (title, language, year,
duration).  The survey-based recommendation engine scores tracks on energy,
valence, primaryMood, genre, region, etc. — so those tracks were invisible
to regular playlists.

This command scans ALL tracks with missing recommendation fields (not just
concert tracks) and fills them in using the heuristic estimator.  It is
safe to run multiple times — only NULL fields are touched.

Usage (inside Docker):
    python manage.py enrich_concert_tracks
    python manage.py enrich_concert_tracks --dry-run
    python manage.py enrich_concert_tracks --artist "Lucky Ali"
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from concerts.enrichment import enrich_track_fields
from tracks.models import Track


class Command(BaseCommand):
    help = "Backfill heuristic audio features on tracks missing recommendation data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many tracks would be updated, without writing to the DB",
        )
        parser.add_argument(
            "--artist",
            type=str,
            default=None,
            help="Only enrich tracks by this artist (name substring match)",
        )
        parser.add_argument(
            "--source",
            type=str,
            default=None,
            choices=["manual", "spotify", "fma"],
            help="Only enrich tracks from this source",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        artist_filter = options.get("artist")
        source_filter = options.get("source")

        # Find tracks that are missing key recommendation fields
        qs = Track.objects.select_related("artistId").filter(
            isActive=True,
        ).filter(
            Q(energy__isnull=True)
            | Q(valence__isnull=True)
            | Q(primaryMood__isnull=True)
            | Q(primaryMood="")
            | Q(genre__isnull=True)
            | Q(genre="")
        )

        if artist_filter:
            qs = qs.filter(artistId__name__icontains=artist_filter)

        if source_filter:
            qs = qs.filter(source=source_filter)

        tracks = list(qs)
        total = len(tracks)
        self.stdout.write(f"Found {total} tracks missing recommendation data.")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to do — all tracks are enriched."))
            return

        if dry_run:
            # Show a sample
            sample = tracks[:10]
            self.stdout.write("\nSample of tracks that would be updated:")
            for t in sample:
                artist_name = getattr(t.artistId, "name", "?") if t.artistId_id else "?"
                self.stdout.write(
                    f"  • {t.title} — {artist_name} "
                    f"[energy={t.energy}, mood={t.primaryMood}, genre={t.genre}]"
                )
            if total > 10:
                self.stdout.write(f"  ... and {total - 10} more")
            self.stdout.write(self.style.WARNING(
                f"\nDRY RUN — {total} tracks would be enriched. Run without --dry-run to apply."
            ))
            return

        updated = 0
        skipped = 0
        for track in tracks:
            try:
                was_updated = enrich_track_fields(track, save=True)
                if was_updated:
                    updated += 1
                else:
                    skipped += 1
            except Exception as exc:
                self.stderr.write(f"  Error enriching track {track.id}: {exc}")
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nDone — enriched {updated} tracks, skipped {skipped}."
        ))
