"""Calibrate the audio engine against Spotify-measured feature references.

The engine's feature formulas use hand-tuned constants. This command tunes
them with data: it reads the song CSVs in ``data/`` (which carry Spotify's
measured energy/valence/acousticness/loudness/tempo), runs OUR engine on the
most popular songs of one language, and fits a per-feature correction —
affine where the engine correlates with the reference, bias-only otherwise.
The result is written to ``tracks/analysis/calibration.json``.

To keep the (engine, truth) pairs clean it samples only **high-popularity**
songs and applies a JioSaavn **match-confidence gate**, so wrong or
alternate recordings are skipped rather than poisoning the fit.

This is a one-time *offline* tuning step. The runtime engine never reads the
CSVs — only the small fitted profile.

Usage (inside Docker):
    docker compose run --rm --no-deps web python manage.py calibrate_audio_engine
    ... --language hindi    # which language's songs to calibrate on
    ... --limit 60          # how many top songs to use (default 60)
    ... --min-match 0.6     # JioSaavn match-confidence gate (0-1)
    ... --delay 1.0         # seconds between downloads
    ... --dry-run           # list the selected songs, fit nothing
    ... --no-write          # fit + report, but don't write calibration.json
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

import numpy as np
from django.core.management.base import BaseCommand

from tracks.analysis.audio_source import AudioAnalysisError, fetch_track_audio
from tracks.analysis.calibration import save_calibration
from tracks.analysis.engine import analyze_audio_bytes

# Features the language CSVs provide a measured reference for.
_CALIBRATED_FEATURES = ("energy", "valence", "acousticness", "loudness")
# Minimum (engine, truth) pairs needed before a correction is trusted.
_MIN_SAMPLES = 8
# Below this |correlation|, a fitted slope is just noise — least-squares
# would collapse the line toward the dataset mean and kill discrimination.
# Weaker than this and we recenter (bias-only) instead of fitting a slope.
_CORR_THRESHOLD = 0.30
# CSV column (lower-cased) -> engine feature name.
_CSV_COLUMNS = {
    "energy": "energy",
    "valence": "valence",
    "acousticness": "acousticness",
    "loudness": "loudness",
    "tempo": "tempo",
}


class Command(BaseCommand):
    help = "Fit the audio engine's calibration profile against data/*_songs.csv"

    def add_arguments(self, parser):
        parser.add_argument("--language", type=str, default="hindi",
                            help="Language to calibrate on (default: hindi)")
        parser.add_argument("--limit", type=int, default=60,
                            help="How many top-popularity songs to use (default: 60)")
        parser.add_argument("--min-match", type=float, default=0.6,
                            help="JioSaavn match-confidence gate, 0-1 (default: 0.6)")
        parser.add_argument("--delay", type=float, default=1.0,
                            help="Seconds between downloads (default: 1.0)")
        parser.add_argument("--dry-run", action="store_true",
                            help="List the sampled songs, fit nothing")
        parser.add_argument("--no-write", action="store_true",
                            help="Fit and report, but do not write calibration.json")

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        limit = options["limit"]
        delay = options["delay"]
        language = options["language"].strip().lower()
        min_match = options["min_match"]
        dry_run = options["dry_run"]
        write = not options["no_write"]

        data_dir = Path(__file__).resolve().parents[3] / "data"
        csv_files = sorted(data_dir.glob("*_songs.csv"))
        if not csv_files:
            self.stderr.write(self.style.ERROR(f"No *_songs.csv found in {data_dir}"))
            return

        rows = [row for f in csv_files for row in self._load_rows(f)]
        self.stdout.write(
            f"Found {len(rows)} reference songs across {len(csv_files)} CSV files."
        )

        sample = self._select_popular(rows, language, limit)
        if not sample:
            self.stderr.write(self.style.ERROR(
                f"No '{language}' songs found in the CSVs — aborting."
            ))
            return
        self.stdout.write(
            f"Selected the {len(sample)} most popular '{language}' songs "
            f"(match gate ≥ {min_match}).\n"
        )

        if dry_run:
            for row in sample[:25]:
                self.stdout.write(
                    f"  • {row['song_name']} — {row['singer']} "
                    f"(popularity {row['popularity']:.0f})"
                )
            if len(sample) > 25:
                self.stdout.write(f"  ... and {len(sample) - 25} more")
            self.stdout.write(self.style.WARNING("\nDRY RUN — nothing fitted."))
            return

        pairs = self._collect_pairs(sample, delay, min_match)
        if not pairs["energy"]:
            self.stderr.write(self.style.ERROR(
                "No songs could be analysed — check network / match gate."
            ))
            return

        corrections, report = self._fit(pairs)
        self._print_report(pairs, report)

        if write and corrections:
            save_calibration(corrections, meta={
                "samples": len(pairs["energy"]),
                "source": f"data/*_songs.csv — top {language} songs",
                "language": language,
                "min_match": min_match,
            })
            self.stdout.write(self.style.SUCCESS(
                "\n✓ Wrote calibration profile -> tracks/analysis/calibration.json"
            ))
        elif not write:
            self.stdout.write(self.style.WARNING("\n--no-write: profile not saved."))

    # ------------------------------------------------------------------
    def _load_rows(self, path: Path) -> list[dict]:
        """Read one CSV, keeping rows with a usable song name + features."""
        rows = []
        with open(path, encoding="utf-8", errors="ignore", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return rows
            # Map lower-cased headers -> actual header keys.
            headers = {(h or "").strip().lower(): h for h in reader.fieldnames}
            if "song_name" not in headers or "energy" not in headers:
                return rows  # not a feature CSV in the expected shape

            for raw in reader:
                song = (raw.get(headers["song_name"]) or "").strip()
                singer = (raw.get(headers.get("singer", "")) or "").strip()
                singer = singer.split("|")[0].strip()  # first credited artist
                if not song:
                    continue
                truth = {}
                for col, feature in _CSV_COLUMNS.items():
                    if col not in headers:
                        continue
                    value = self._to_float(raw.get(headers[col]))
                    if value is not None:
                        truth[feature] = value
                if "energy" not in truth:
                    continue
                lang = (raw.get(headers.get("language", "")) or "").strip().lower()
                popularity = self._to_float(raw.get(headers.get("popularity", "")))
                streams = self._to_float(raw.get(headers.get("stream", "")))
                rows.append({
                    "song_name": song, "singer": singer, "truth": truth,
                    "language": lang, "popularity": popularity or 0.0,
                    "streams": streams or 0.0, "_file": path.name,
                })
        return rows

    @staticmethod
    def _to_float(value):
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None

    def _select_popular(self, rows, language, limit) -> list[dict]:
        """Top ``limit`` most-popular songs in ``language``, de-duplicated.

        Popular songs are the ones JioSaavn reliably has the canonical
        recording of — which keeps the (engine, truth) pairs honest.
        """
        seen, pool = set(), []
        for row in rows:
            if language and row["language"] != language:
                continue
            key = (row["song_name"].lower(), row["singer"].lower())
            if key in seen:
                continue
            seen.add(key)
            pool.append(row)
        pool.sort(key=lambda r: (r["popularity"], r["streams"]), reverse=True)
        return pool[:limit]

    def _collect_pairs(self, sample, delay, min_match) -> dict:
        """Analyse each song; return ``{feature: [(engine, truth), ...]}``."""
        pairs = {f: [] for f in (*_CALIBRATED_FEATURES, "tempo")}
        ok = low_match = fail = 0

        for i, row in enumerate(sample, 1):
            label = f"{row['song_name']} — {row['singer']}"
            self.stdout.write(f"[{i}/{len(sample)}] {label}")
            try:
                audio_bytes, _ = fetch_track_audio(
                    row["song_name"], row["singer"], min_match=min_match)
                # calibrated=False: fit corrections on the engine's RAW output.
                features = analyze_audio_bytes(audio_bytes, calibrated=False)
            except AudioAnalysisError as exc:
                if "match confidence" in str(exc):
                    low_match += 1
                else:
                    fail += 1
                self.stdout.write(self.style.WARNING(f"    skipped — {exc}"))
                continue
            except Exception as exc:  # noqa: BLE001 - keep the batch going
                self.stdout.write(self.style.WARNING(f"    failed — {exc}"))
                fail += 1
                continue

            for feature in (*_CALIBRATED_FEATURES, "tempo"):
                truth = row["truth"].get(feature)
                engine = features.get("tempoBpm" if feature == "tempo" else feature)
                if truth is not None and engine is not None:
                    pairs[feature].append((float(engine), float(truth)))
            ok += 1
            if i < len(sample) and delay > 0:
                time.sleep(delay)

        self.stdout.write(
            f"\nAnalysed {ok} songs — {low_match} rejected by match gate, "
            f"{fail} other failures."
        )
        return pairs

    def _fit(self, pairs) -> tuple[dict, dict]:
        """Least-squares affine fit per feature; returns (corrections, report)."""
        corrections, report = {}, {}

        for feature in _CALIBRATED_FEATURES:
            data = pairs[feature]
            if len(data) < _MIN_SAMPLES:
                report[feature] = {"n": len(data), "skipped": True}
                continue

            engine = np.array([d[0] for d in data])
            truth = np.array([d[1] for d in data])

            mae_before = float(np.mean(np.abs(engine - truth)))
            bias = float(np.mean(engine - truth))
            corr = (float(np.corrcoef(engine, truth)[0, 1])
                    if np.std(engine) > 1e-9 else 0.0)

            # Only fit a slope when the engine actually correlates with the
            # reference. Otherwise recenter (slope=1) so we fix the
            # systematic offset without collapsing the engine's spread.
            if abs(corr) >= _CORR_THRESHOLD and np.std(engine) > 1e-9:
                slope, intercept = (float(x) for x in np.polyfit(engine, truth, 1))
                method = "affine"
            else:
                slope, intercept = 1.0, float(np.mean(truth) - np.mean(engine))
                method = "bias-only"

            corrected = slope * engine + intercept
            mae_after = float(np.mean(np.abs(corrected - truth)))

            corrections[feature] = {
                "slope": round(slope, 5),
                "intercept": round(intercept, 5),
                "method": method,
                "mae_before": round(mae_before, 4),
                "mae_after": round(mae_after, 4),
                "samples": len(data),
            }
            report[feature] = {
                "n": len(data), "skipped": False, "bias": bias, "corr": corr,
                "mae_before": mae_before, "mae_after": mae_after,
                "slope": slope, "intercept": intercept, "method": method,
            }

        # Tempo: report-only (octave errors are a Tier-3 deterministic fix).
        report["tempo"] = self._tempo_report(pairs["tempo"])
        return corrections, report

    @staticmethod
    def _tempo_report(data) -> dict:
        if not data:
            return {"n": 0}
        exact = octave = 0
        for engine, truth in data:
            if truth <= 0:
                continue
            ratios = [truth, truth / 2, truth * 2, truth / 3, truth * 3]
            if abs(engine - truth) / truth <= 0.04:
                exact += 1
            if any(abs(engine - r) / max(r, 1e-6) <= 0.04 for r in ratios):
                octave += 1
        return {"n": len(data), "exact": exact, "octave": octave}

    def _print_report(self, pairs, report):
        self.stdout.write("\n" + "=" * 64)
        self.stdout.write("CALIBRATION REPORT")
        self.stdout.write("=" * 64)
        self.stdout.write(
            f"{'feature':<14}{'n':>4}{'MAE before':>12}{'MAE after':>11}"
            f"{'corr':>8}{'bias':>9}   method"
        )
        for feature in _CALIBRATED_FEATURES:
            r = report.get(feature, {})
            if r.get("skipped"):
                self.stdout.write(f"{feature:<14}{r['n']:>4}   too few samples")
                continue
            self.stdout.write(
                f"{feature:<14}{r['n']:>4}{r['mae_before']:>12.4f}"
                f"{r['mae_after']:>11.4f}{r['corr']:>8.2f}{r['bias']:>9.3f}"
                f"   {r['method']}"
            )
        t = report.get("tempo", {})
        if t.get("n"):
            self.stdout.write(
                f"\ntempo: {t['exact']}/{t['n']} within 4% exact, "
                f"{t['octave']}/{t['n']} resolvable allowing octave folds "
                f"(octave correction is a Tier-3 fix)."
            )
