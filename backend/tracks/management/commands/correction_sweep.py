"""Re-analyse tracks that need correction.

Two pools:

  1. Tracks whose engine output sits out of range (e.g. negative
     ``acousticness`` written before the calibration clamp was tightened).
     Re-analysed with ``force=True``.
  2. ``source=manual`` tracks that pre-date the engine and lack the
     deterministic features (``tempoBpm``, ``loudness``,
     ``instrumentalness``). Analysed normally (the engine fills them in).

Always writes :class:`AudioFeatureSnapshot` rows for every analysed run.

Designed to run unattended for hours — accepts ``--delay`` to throttle
JioSaavn and prints a progress line every track. Safe to re-run; tracks
that already look healthy after a previous sweep are skipped.

Usage (inside Docker):

    python manage.py correction_sweep --delay 1.0 --limit 50
    python manage.py correction_sweep              # the full sweep
"""
from __future__ import annotations

import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections, connection
from django.db.models import Q

from tracks.analysis import analyze_track
from tracks.models import Track


class Command(BaseCommand):
    help = "Re-analyse out-of-range and feature-incomplete tracks."

    def add_arguments(self, parser):
        parser.add_argument("--delay", type=float, default=0.8)
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument(
            "--corrupted-only",
            action="store_true",
            help="Only re-analyse tracks with out-of-range values (skip pool 2).",
        )
        parser.add_argument(
            "--incomplete-only",
            action="store_true",
            help="Only analyse manual-source tracks missing deterministic features.",
        )

    def _collect(self, options) -> tuple[list[Track], list[Track]]:
        # Out-of-range pool — these must be re-analysed with force=True so
        # the engine overwrites the bad values.
        corrupted_qs = Track.objects.filter(
            isActive=True,
        ).filter(
            Q(acousticness__lt=0)
            | Q(acousticness__gt=1)
            | Q(energy__lt=0)
            | Q(energy__gt=1)
            | Q(valence__lt=0)
            | Q(valence__gt=1)
            | Q(instrumentalness__lt=0)
            | Q(instrumentalness__gt=1)
            | Q(loudness__lt=-60)
            | Q(loudness__gt=0)
        ).select_related("artistId")
        corrupted = list(corrupted_qs)

        # Feature-incomplete pool — manual-source tracks missing the
        # deterministic engine fields. analyse_track skips already-complete
        # tracks unless force=True, so this is safe without --force.
        incomplete_qs = Track.objects.filter(
            isActive=True,
            source="manual",
        ).filter(
            Q(tempoBpm__isnull=True)
            | Q(loudness__isnull=True)
            | Q(instrumentalness__isnull=True)
        ).exclude(
            # Exclude corrupted (they're already in the other pool — avoids
            # double-analysing) and tracks without a title.
            id__in=[t.id for t in corrupted],
        ).exclude(title__isnull=True).select_related("artistId")

        # Order by has-stream-url first so the cheap ones run first.
        incomplete_qs = incomplete_qs.extra(
            select={
                "has_url": "CASE WHEN stream_url IS NOT NULL THEN 0 ELSE 1 END"
            },
        ).order_by("has_url", "id")
        incomplete = list(incomplete_qs)

        if options["corrupted_only"]:
            incomplete = []
        if options["incomplete_only"]:
            corrupted = []
        return corrupted, incomplete

    def _analyse_with_retry(self, track: Track, *, force: bool):
        """Wrap ``analyze_track`` with a single retry on DB connection drops.

        Postgres sometimes EOFs the connection mid-analysis. ``analyze_track``
        swallows broad exceptions and returns ``None``, so we close the
        stale connection and refetch the track on the second attempt.
        """
        from django.db.utils import InterfaceError, OperationalError

        try:
            return analyze_track(track, force=force)
        except (InterfaceError, OperationalError):
            # Force a clean connection and refetch the track row.
            connection.close()
            close_old_connections()
            track.refresh_from_db()
            return analyze_track(track, force=force)

    def handle(self, *args, **options):
        delay = options["delay"]
        limit = options["limit"]

        corrupted, incomplete = self._collect(options)
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Correction sweep — corrupted={len(corrupted)} "
            f"incomplete={len(incomplete)}"
        ))

        plan = [("FORCE", t) for t in corrupted] + [("FILL", t) for t in incomplete]
        if limit:
            plan = plan[:limit]
        total = len(plan)

        analyzed = failed = skipped = 0
        t0 = time.monotonic()

        for i, (mode, track) in enumerate(plan, 1):
            # librosa work can take 15+ seconds with no DB activity, long
            # enough for Postgres to drop idle connections. Force-close any
            # stale connection before each iteration so the next ORM call
            # transparently reopens a fresh one.
            close_old_connections()

            artist_name = (
                track.artistId.name if track.artistId else "?"
            ) or "?"
            self.stdout.write(
                f"[{i}/{total}] {mode} {track.title} — {artist_name}"
            )
            try:
                # FORCE on both pools: corrupted needs overwriting, and
                # the incomplete pool's energy/valence/tempo came from
                # legacy imports (not the engine), so we want engine output
                # everywhere instead of a half-engine-half-import mix.
                result = self._analyse_with_retry(track, force=True)
                if result:
                    self.stdout.write(self.style.SUCCESS(
                        f"  ✓ E={result['energy']:.2f} V={result['valence']:.2f} "
                        f"T={result['tempoBpm']} A={result['acousticness']:.2f} "
                        f"I={result['instrumentalness']:.2f} L={result['loudness']:.1f} "
                        f"mood={result['primaryMood']} genre={result['genre']}"
                    ))
                    analyzed += 1
                else:
                    skipped += 1
                    self.stdout.write("  ⊘ skipped")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                self.stderr.write(self.style.ERROR(f"  ✗ {exc!r}"))

            if delay > 0 and i < total:
                time.sleep(delay)

            # Periodic ETA line every 25 tracks
            if i % 25 == 0:
                elapsed = time.monotonic() - t0
                rate = i / elapsed
                eta_min = (total - i) / rate / 60 if rate > 0 else 0
                self.stdout.write(self.style.WARNING(
                    f"  -- progress {i}/{total} -- {rate:.2f} tracks/s -- "
                    f"ETA ~{eta_min:.0f} min --"
                ))

        elapsed = round(time.monotonic() - t0, 1)
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS(
            f"DONE in {elapsed}s — analyzed={analyzed} skipped={skipped} failed={failed}"
        ))
