"""Re-predict valence (and re-derive primaryMood) for already-analysed tracks
from their STORED feature vectors — no audio re-download required.

WHY
---
The old in-house valence estimator was a heuristic whose "major key = happy"
assumption inflated valence on this (largely major-key) catalogue — it scored
Pearson -0.07 against Spotify ground truth, worse than predicting the mean.
That inflated valence stamped a huge share of the catalogue "celebratory" and
is the main reason recommendations didn't fit the mood. The retrained model
(`train_audio_models`, RandomForest, CV Pearson ~+0.74) fixes the estimator.

Every analysed track already has its full DSP `featureVector` saved in an
`AudioFeatureSnapshot`, so we can re-run JUST the valence model over the stored
vectors and refresh `valence` + `primaryMood` — without touching audio.

ORDER OF OPERATIONS
-------------------
1. Retrain the model in an env with the project's pinned scikit-learn:
       python manage.py train_audio_models --skip-genre
   (writes tracks/analysis/trained/valence.joblib)
2. Preview, then apply:
       python manage.py repredict_valence            # dry-run
       python manage.py repredict_valence --apply     # writes + CSV backup

SAFETY
------
* Dry-run by default; prints the valence shift + before/after mood mix.
* --apply writes a reversible CSV backup (id, old_valence, new_valence,
  old_mood, new_mood) before any update, and writes inside one transaction.
* Only tracks with a stored featureVector are touched; the model must exist.
"""
from __future__ import annotations

import csv
import os
from collections import Counter
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Re-predict valence from stored feature vectors and re-derive primaryMood (dry-run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Write the new valence/mood (default is a dry-run preview).")
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--backup-dir", default=None)

    def handle(self, *args, **options):
        import numpy as np

        from tracks.analysis.classifiers import get_estimator
        from tracks.analysis.training import (
            FEATURE_NAMES, MODELS_DIR, feature_dict_from_result, features_to_array,
        )
        from tracks.models import AudioFeatureSnapshot, Track

        # Re-derive mood with the SAME estimator the engine used to label these
        # tracks (nearest-prototype), so the refreshed labels stay consistent
        # with analyze_track — not the import-path threshold rule, which
        # over-collapses this catalogue's mid-energy tracks into "focused".
        mood_estimator = get_estimator("mood")

        model_path = MODELS_DIR / "valence.joblib"
        if not model_path.exists():
            raise CommandError(
                f"No trained model at {model_path}. Run 'python manage.py "
                "train_audio_models --skip-genre' first."
            )
        import joblib
        model = joblib.load(model_path)

        apply_changes = options["apply"]
        batch = options["batch_size"]

        qs = Track.objects.filter(featuresSyncedAt__isnull=False, energy__isnull=False)
        total = qs.count()

        v_before, v_after = [], []
        mood_before, mood_after = Counter(), Counter()
        changes = []  # (id, title, old_v, new_v, old_mood, new_mood)
        skipped_no_vector = 0

        for track in qs.iterator(chunk_size=batch):
            snap = (AudioFeatureSnapshot.objects.filter(trackId=track)
                    .order_by("-syncedAt").values_list("snapshot", flat=True).first())
            if not isinstance(snap, dict) or "featureVector" not in snap:
                skipped_no_vector += 1
                continue
            feats = feature_dict_from_result(snap)
            arr = features_to_array(feats).reshape(1, -1)
            new_v = round(float(np.clip(model.predict(arr)[0], 0.0, 1.0)), 4)
            new_mood = mood_estimator.predict(
                {"energy": track.energy, "valence": new_v}
            ).label

            v_before.append(track.valence if track.valence is not None else float("nan"))
            v_after.append(new_v)
            mood_before[track.primaryMood or "—"] += 1
            mood_after[new_mood or "—"] += 1
            if new_v != track.valence or new_mood != track.primaryMood:
                changes.append((str(track.id), track.title or "", track.valence,
                                new_v, track.primaryMood or "", new_mood or ""))

        self._summary(np, v_before, v_after, mood_before, mood_after,
                      total, skipped_no_vector, len(changes))

        if not changes:
            self.stdout.write(self.style.SUCCESS("Nothing to change."))
            return
        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                f"\nDRY-RUN: {len(changes)} track(s) WOULD change. Re-run with --apply."
            ))
            return

        backup = self._backup(changes, options.get("backup_dir"))
        self.stdout.write(self.style.SUCCESS(f"Backup written: {backup}"))

        by_id = {c[0]: (c[3], c[5]) for c in changes}  # id -> (new_v, new_mood)
        updated = 0
        with transaction.atomic():
            buf = []
            for track in Track.objects.filter(id__in=list(by_id)).iterator(chunk_size=batch):
                new_v, new_mood = by_id[str(track.id)]
                track.valence = new_v
                track.primaryMood = new_mood
                buf.append(track)
                if len(buf) >= batch:
                    Track.objects.bulk_update(buf, ["valence", "primaryMood"])
                    updated += len(buf); buf = []
            if buf:
                Track.objects.bulk_update(buf, ["valence", "primaryMood"])
                updated += len(buf)
        self.stdout.write(self.style.SUCCESS(f"Applied: {updated} track(s) updated."))
        self.stdout.write(f"Revert from {backup} if needed.")

    # ── helpers ──────────────────────────────────────────────────────────
    def _summary(self, np, vb, va, mb, ma, total, skipped, n_changes):
        vb = np.array([x for x in vb if x == x])  # drop NaN
        va = np.array(va)
        self.stdout.write("")
        self.stdout.write(f"Analysed tracks considered : {total}")
        self.stdout.write(f"Skipped (no stored vector) : {skipped}")
        self.stdout.write(f"Tracks that would change   : {n_changes}")
        if len(va):
            self.stdout.write(
                f"\nvalence median: current {np.median(vb):.2f} -> repaired {np.median(va):.2f}"
                f"   (p25 {np.percentile(vb,25):.2f}->{np.percentile(va,25):.2f}, "
                f"p75 {np.percentile(vb,75):.2f}->{np.percentile(va,75):.2f})"
            )
        self.stdout.write(f"\n  {'mood':12s} {'before':>8s} {'after':>8s}")
        for m in sorted(set(mb) | set(ma)):
            self.stdout.write(f"  {m:12s} {mb.get(m,0):8d} {ma.get(m,0):8d}")

    def _backup(self, changes, backup_dir):
        base = backup_dir or os.path.join(getattr(settings, "BASE_DIR", "."), "data")
        os.makedirs(base, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(base, f"valence_mood_backup_{stamp}.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "title", "old_valence", "new_valence", "old_mood", "new_mood"])
            w.writerows(changes)
        return path
