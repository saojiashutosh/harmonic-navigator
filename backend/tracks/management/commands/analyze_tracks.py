"""Analyze tracks with REAL audio features using librosa.

Downloads each song's audio from JioSaavn, runs spectral analysis via
librosa, and writes genuine energy/valence/tempo/key/mood values to the DB.

This replaces the heuristic estimates with real signal-processing data.

Usage (inside Docker):
    # Analyze all tracks missing audio features
    python manage.py analyze_tracks

    # Analyze with a limit (batch processing)
    python manage.py analyze_tracks --limit 50

    # Force re-analyze tracks that already have features
    python manage.py analyze_tracks --force

    # Analyze only tracks by a specific artist
    python manage.py analyze_tracks --artist "Arijit Singh"

    # Dry run — show what would be analyzed
    python manage.py analyze_tracks --dry-run

    # Analyze concert-sourced (manual) tracks only
    python manage.py analyze_tracks --source manual
"""
import time

from django.core.management.base import BaseCommand
from django.db.models import Q

from tracks.analysis import analyze_track
from tracks.models import Track


class Command(BaseCommand):
    help = "Download songs and extract REAL audio features using librosa analysis"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of tracks to analyze (for batch processing)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show which tracks would be analyzed without doing it",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-analyze tracks that already have audio features",
        )
        parser.add_argument(
            "--artist",
            type=str,
            default=None,
            help="Only analyze tracks by this artist (name substring match)",
        )
        parser.add_argument(
            "--source",
            type=str,
            default=None,
            choices=["manual", "spotify", "fma"],
            help="Only analyze tracks from this source",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.5,
            help="Seconds to wait between downloads (be kind to JioSaavn). Default: 1.5",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        dry_run = options["dry_run"]
        force = options["force"]
        artist_filter = options.get("artist")
        source_filter = options.get("source")
        delay = options["delay"]

        # Build queryset
        qs = Track.objects.select_related("artistId").filter(isActive=True)

        if not force:
            # Only tracks missing key audio features
            qs = qs.filter(
                Q(energy__isnull=True)
                | Q(valence__isnull=True)
                | Q(tempoBpm__isnull=True)
            )

        if artist_filter:
            qs = qs.filter(artistId__name__icontains=artist_filter)

        if source_filter:
            qs = qs.filter(source=source_filter)

        # Order by tracks with stream URLs first (faster — no JioSaavn search)
        qs = qs.extra(
            select={"has_url": "CASE WHEN stream_url IS NOT NULL THEN 0 ELSE 1 END"},
        ).order_by("has_url", "id")

        if limit:
            qs = qs[:limit]

        tracks = list(qs)
        total = len(tracks)

        self.stdout.write(f"Found {total} tracks to analyze.")

        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                "Nothing to do — all tracks have audio features."
            ))
            return

        if dry_run:
            sample = tracks[:15]
            self.stdout.write("\nTracks that would be analyzed:")
            for t in sample:
                artist_name = getattr(t.artistId, "name", "?") if t.artistId_id else "?"
                has_url = "✓ cached URL" if t.streamUrl else "⟳ needs search"
                self.stdout.write(
                    f"  • {t.title} — {artist_name} [{has_url}]"
                )
            if total > 15:
                self.stdout.write(f"  ... and {total - 15} more")
            self.stdout.write(self.style.WARNING(
                f"\nDRY RUN — {total} tracks would be analyzed."
            ))
            return

        analyzed = 0
        failed = 0
        skipped = 0

        for i, track in enumerate(tracks, 1):
            artist_name = getattr(track.artistId, "name", "?") if track.artistId_id else "?"
            self.stdout.write(
                f"\n[{i}/{total}] Analyzing: {track.title} — {artist_name}"
            )

            try:
                result = analyze_track(track, force=force)
                if result:
                    self.stdout.write(self.style.SUCCESS(
                        f"  ✓ energy={result['energy']:.2f} "
                        f"valence={result['valence']:.2f} "
                        f"tempo={result['tempoBpm']} "
                        f"mood={result['primaryMood']} "
                        f"genre={result['genre']} "
                        f"region={result['region']} "
                        f"key={result['keySignature']}"
                    ))
                    analyzed += 1
                else:
                    self.stdout.write(self.style.WARNING("  ⊘ Skipped (already analyzed or no title)"))
                    skipped += 1
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"  ✗ Failed: {exc}"))
                failed += 1

            # Rate-limit to be kind to JioSaavn
            if i < total and delay > 0:
                time.sleep(delay)

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(
            f"Done — analyzed: {analyzed}, skipped: {skipped}, failed: {failed}"
        ))
