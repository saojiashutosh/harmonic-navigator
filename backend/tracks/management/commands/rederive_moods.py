"""Re-derive Track.primaryMood from measured audio features.

WHY
---
~42% of the catalogue was bulk-stamped with a default mood (mostly
"energized") and never measured, and among tracks that *do* have features the
stored primaryMood disagreed with its own energy/valence ~43% of the time.
The recommendation engine matches on primaryMood, so those wrong labels are
the dominant reason playlists feel off-mood.

This command recomputes primaryMood — using the SAME rule new imports use
(`tracks.services.derive_primary_mood`) — but ONLY for tracks that actually
have measured `energy` and `valence`. Tracks with NULL features are left
untouched on purpose: there is nothing to re-derive from, and the engine now
down-ranks those unverified labels itself.

SAFETY
------
* Dry-run by DEFAULT — prints the before/after mood distribution and the
  number of tracks that would change, and writes NOTHING.
* Pass --apply to actually write. Before writing it dumps every
  (id, title, old_mood, new_mood) to a timestamped CSV under data/ so the
  change is fully reversible.
* Only rows whose label actually changes are updated.

Examples
--------
    python manage.py rederive_moods                 # preview only
    python manage.py rederive_moods --apply          # write + back up
    python manage.py rederive_moods --apply --backup-dir /tmp
"""
from __future__ import annotations

import csv
import os
from collections import Counter
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Re-derive Track.primaryMood from measured energy/valence (dry-run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually write the new labels (default is a dry-run preview).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Rows per bulk_update batch (default 500).",
        )
        parser.add_argument(
            "--backup-dir",
            default=None,
            help="Directory for the reversible CSV backup (default: <BASE_DIR>/data).",
        )

    def handle(self, *args, **options):
        # Imported here so the command module stays importable even if the
        # Spotify client (pulled in by tracks.services) is unavailable.
        from tracks.models import Track
        from tracks.services import derive_primary_mood

        apply_changes = options["apply"]
        batch_size = options["batch_size"]

        qs = Track.objects.filter(energy__isnull=False, valence__isnull=False)
        total = qs.count()
        skipped = Track.objects.filter(
            energy__isnull=True
        ).count() + Track.objects.filter(
            energy__isnull=False, valence__isnull=True
        ).count()

        before = Counter()
        after = Counter()
        changes = []  # (id, title, old, new)

        for track in qs.iterator(chunk_size=batch_size):
            old = track.primaryMood
            new = derive_primary_mood({"energy": track.energy, "valence": track.valence})
            before[old or "—"] += 1
            after[new or "—"] += 1
            if new != old:
                changes.append((str(track.id), track.title or "", old or "", new or ""))

        self._print_distribution(before, after, total, skipped, len(changes))

        if not changes:
            self.stdout.write(self.style.SUCCESS("Nothing to change — labels already match the rule."))
            return

        if not apply_changes:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDRY-RUN: {len(changes)} track(s) WOULD change. "
                    "Re-run with --apply to write (a CSV backup is saved first)."
                )
            )
            self._preview_changes(changes)
            return

        backup_path = self._write_backup(changes, options.get("backup_dir"))
        self.stdout.write(self.style.SUCCESS(f"Backup written: {backup_path}"))

        changed_map = {cid: new for cid, _title, _old, new in changes}
        updated = 0
        with transaction.atomic():
            buffer = []
            for track in Track.objects.filter(id__in=list(changed_map)).iterator(chunk_size=batch_size):
                track.primaryMood = changed_map[str(track.id)]
                buffer.append(track)
                if len(buffer) >= batch_size:
                    Track.objects.bulk_update(buffer, ["primaryMood"])
                    updated += len(buffer)
                    buffer = []
            if buffer:
                Track.objects.bulk_update(buffer, ["primaryMood"])
                updated += len(buffer)

        self.stdout.write(self.style.SUCCESS(f"Applied: {updated} track(s) re-labelled."))
        self.stdout.write(f"To revert: restore the primaryMood column from {backup_path}.")

    # ── helpers ──────────────────────────────────────────────────────────
    def _print_distribution(self, before, after, total, skipped, n_changes):
        moods = sorted(set(before) | set(after))
        self.stdout.write("")
        self.stdout.write(f"Feature-backed tracks considered : {total}")
        self.stdout.write(f"NULL-feature tracks skipped       : {skipped}")
        self.stdout.write(f"Tracks whose label changes        : {n_changes}")
        self.stdout.write("")
        self.stdout.write(f"  {'mood':14s} {'before':>8s} {'after':>8s} {'delta':>8s}")
        for m in moods:
            b, a = before.get(m, 0), after.get(m, 0)
            self.stdout.write(f"  {m:14s} {b:8d} {a:8d} {a - b:+8d}")

    def _preview_changes(self, changes, limit=15):
        self.stdout.write("\n  sample changes (old -> new):")
        for cid, title, old, new in changes[:limit]:
            self.stdout.write(f"    {title[:42]:42s} {old:12s} -> {new}")
        if len(changes) > limit:
            self.stdout.write(f"    … and {len(changes) - limit} more")

    def _write_backup(self, changes, backup_dir):
        base = backup_dir or os.path.join(getattr(settings, "BASE_DIR", "."), "data")
        os.makedirs(base, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(base, f"primaryMood_backup_{stamp}.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["id", "title", "old_primaryMood", "new_primaryMood"])
            writer.writerows(changes)
        return path
