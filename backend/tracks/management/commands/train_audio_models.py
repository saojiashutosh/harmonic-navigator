"""Train the audio engine's valence + genre models on the JSONL dataset.

Reads ``tracks/analysis/training_data/{valence,genre}.jsonl`` (produced by
``build_training_dataset``), trains scikit-learn models, evaluates them
with cross-validation, and writes:

    tracks/analysis/trained/valence.joblib
    tracks/analysis/trained/genre.joblib
    tracks/analysis/trained/meta.json

Once written, the engine's default estimators (``ModelValenceRegressor`` /
``ModelGenreClassifier``) auto-detect the joblib files and use them in
place of the heuristics — no settings change required.

Usage (inside Docker):
    docker compose run --rm --no-deps web python manage.py train_audio_models
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
from django.core.management.base import BaseCommand

from tracks.analysis.training import (
    DATASET_DIR,
    FEATURE_NAMES,
    MODELS_DIR,
    load_jsonl,
)


class Command(BaseCommand):
    help = "Train the valence regressor and genre classifier from the JSONL dataset."

    def add_arguments(self, parser):
        parser.add_argument("--skip-valence", action="store_true")
        parser.add_argument("--skip-genre", action="store_true")
        parser.add_argument("--cv-folds", type=int, default=5,
                            help="Cross-validation folds (default: 5)")

    def handle(self, *args, **opt):
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        cv = opt["cv_folds"]
        meta: dict = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "feature_names": FEATURE_NAMES,
        }

        if not opt["skip_valence"]:
            meta["valence"] = self._train_valence(cv)
        if not opt["skip_genre"]:
            meta["genre"] = self._train_genre(cv)

        with open(MODELS_DIR / "meta.json", "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)
        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Wrote model metadata -> {MODELS_DIR / 'meta.json'}"
        ))

    # ------------------------------------------------------------------
    def _train_valence(self, cv: int) -> dict:
        import joblib
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.model_selection import cross_val_predict, cross_val_score

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n=== Training valence regressor ==="
        ))
        path = DATASET_DIR / "valence.jsonl"
        rows = load_jsonl(path)
        if len(rows) < 30:
            self.stderr.write(self.style.WARNING(
                f"Too few rows ({len(rows)}) — skipping valence training."
            ))
            return {"skipped": True, "samples": len(rows)}

        X = np.array(
            [[r["features"].get(n, 0.0) for n in FEATURE_NAMES] for r in rows],
            dtype=float,
        )
        y = np.array([float(r["valence"]) for r in rows])

        # RandomForest beat GradientBoosting / Ridge in 5-fold CV on this set
        # (MAE 0.147 / Pearson +0.74 vs GB 0.156 / +0.70), and — crucially —
        # its predictions stay inside the training valence range, so it does
        # NOT extrapolate to the inflated values the old heuristic produced on
        # major-key Bollywood (heuristic scored Pearson -0.07, worse than just
        # predicting the mean). Tree features (beat_strength, percussive_ratio,
        # energy, acousticness) carry the real signal; "major key = happy" did
        # not.
        model = RandomForestRegressor(
            n_estimators=400, min_samples_leaf=2, random_state=42, n_jobs=-1,
        )
        # k-fold CV using negative MAE — sign-flipped back for reporting.
        mae_scores = -cross_val_score(model, X, y, cv=cv,
                                      scoring="neg_mean_absolute_error")
        r2_scores = cross_val_score(model, X, y, cv=cv, scoring="r2")
        cv_pred = np.clip(cross_val_predict(model, X, y, cv=cv), 0.0, 1.0)
        cv_pearson = (
            float(np.corrcoef(cv_pred, y)[0, 1]) if np.std(cv_pred) > 1e-9 else 0.0
        )

        baseline_mae = float(np.mean(np.abs(y - np.mean(y))))
        cv_mae = float(np.mean(mae_scores))
        cv_r2 = float(np.mean(r2_scores))

        # Final model trained on the full dataset.
        model.fit(X, y)
        out = MODELS_DIR / "valence.joblib"
        joblib.dump(model, out, compress=3)

        self.stdout.write(f"  samples       {len(rows)}")
        self.stdout.write(f"  baseline MAE  {baseline_mae:.4f}   (predict the mean)")
        self.stdout.write(f"  CV MAE        {cv_mae:.4f}   (over {cv} folds)")
        self.stdout.write(f"  CV R²         {cv_r2:+.3f}")
        self.stdout.write(f"  CV Pearson    {cv_pearson:+.3f}   (vs heuristic -0.07)")
        self.stdout.write(self.style.SUCCESS(f"  saved -> {out.name}"))
        return {
            "samples": len(rows),
            "cv_mae": cv_mae,
            "cv_r2": cv_r2,
            "cv_pearson": cv_pearson,
            "baseline_mae": baseline_mae,
        }

    # ------------------------------------------------------------------
    def _train_genre(self, cv: int) -> dict:
        import joblib
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import classification_report
        from sklearn.model_selection import cross_val_score, cross_val_predict

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n=== Training genre classifier ==="
        ))
        path = DATASET_DIR / "genre.jsonl"
        rows = load_jsonl(path)
        if len(rows) < 30:
            self.stderr.write(self.style.WARNING(
                f"Too few rows ({len(rows)}) — skipping genre training."
            ))
            return {"skipped": True, "samples": len(rows)}

        X = np.array(
            [[r["features"].get(n, 0.0) for n in FEATURE_NAMES] for r in rows],
            dtype=float,
        )
        y = np.array([r["genre"] for r in rows])

        model = RandomForestClassifier(
            n_estimators=400, max_depth=None, min_samples_leaf=2,
            class_weight="balanced", n_jobs=-1, random_state=42,
        )
        # Skip CV if any class has too few members for the chosen fold count.
        unique, counts = np.unique(y, return_counts=True)
        smallest = int(counts.min())
        folds = min(cv, smallest) if smallest >= 2 else 0

        acc = None
        report = "(CV skipped — too few samples per class)"
        if folds >= 2:
            acc = float(np.mean(cross_val_score(model, X, y, cv=folds,
                                                scoring="accuracy")))
            preds = cross_val_predict(model, X, y, cv=folds)
            report = classification_report(y, preds, zero_division=0)

        model.fit(X, y)
        out = MODELS_DIR / "genre.joblib"
        joblib.dump(model, out, compress=3)

        self.stdout.write(f"  samples           {len(rows)}")
        self.stdout.write(f"  classes ({len(unique)}): "
                          + ", ".join(f"{c}={n}" for c, n in zip(unique, counts)))
        if acc is not None:
            self.stdout.write(f"  CV accuracy        {acc:+.3f}   (over {folds} folds)")
        self.stdout.write("\n  Per-class CV report:")
        for line in report.splitlines():
            self.stdout.write("    " + line)
        self.stdout.write(self.style.SUCCESS(f"\n  saved -> {out.name}"))
        return {
            "samples": len(rows),
            "cv_accuracy": acc,
            "classes": list(unique),
            "class_counts": [int(n) for n in counts],
        }
