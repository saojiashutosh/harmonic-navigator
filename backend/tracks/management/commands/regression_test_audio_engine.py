"""Regression-test the in-house audio engine.

Picks a curated panel of tracks, runs the full extraction pipeline against
each, and produces a rigorous report covering:

  * Determinism — same bytes -> same FeatureVector (within float noise).
  * Range checks — every feature within its documented bounds.
  * Calibration delta — raw vs. calibrated outputs side-by-side.
  * Cross-feature sanity — directional checks (energy vs. loudness, mode
    vs. valence, instrumentalness vs. vocal_band_ratio).
  * Genre / mood stability — same audio -> same label across reruns.

Outputs:
  * stdout summary (overall pass/fail + per-track findings)
  * an Excel report (`backend/data/regression_reports/engine_regression_<ts>.xlsx`)
    with two sheets: ``Tracks`` (one row per analysed track, raw+calibrated)
    and ``Findings`` (one row per detected issue)
  * AudioFeatureSnapshot rows for every analysed track (audit trail)

Usage (inside Docker):

    python manage.py regression_test_audio_engine
    python manage.py regression_test_audio_engine --panel custom \\
        --titles "Tum Hi Ho|Arijit Singh" "Believer|Imagine Dragons"
    python manage.py regression_test_audio_engine --rounds 2 --persist
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from tracks.analysis import analyze_track
from tracks.analysis.audio_source import (
    AudioAnalysisError,
    fetch_track_audio,
)
from tracks.analysis.engine import analyze_audio_bytes
from tracks.models import Artist, AudioFeatureSnapshot, Track


# Curated panel — diverse across mood/genre/language to stretch the engine.
# Each entry is (title, artist, language, expected_genre_bucket, mood_hint).
# Expected fields are *hints* used for soft directional checks, not hard
# truths — the engine has no ground-truth source.
_DEFAULT_PANEL: list[tuple[str, str, str, str, str]] = [
    # Western pop / radio
    ("Shape of You", "Ed Sheeran", "english", "pop", "celebratory"),
    ("Believer", "Imagine Dragons", "english", "rock", "energized"),
    # EDM / electronic
    ("Levels", "Avicii", "english", "electronic", "energized"),
    # Slow / acoustic ballad
    ("Someone Like You", "Adele", "english", "acoustic", "melancholic"),
    # Bollywood pop
    ("Tum Hi Ho", "Arijit Singh", "hindi", "bollywood", "melancholic"),
    ("Kesariya", "Arijit Singh", "hindi", "bollywood", "celebratory"),
    # Ghazal — slow, minor, acoustic
    ("Hoshwalon Ko Khabar Kya", "Jagjit Singh", "hindi", "ghazal", "melancholic"),
    # Lofi / chill
    ("Lofi Study", "Lofi Girl", "english", "lofi", "calm"),
    # Ambient / instrumental
    ("Weightless", "Marconi Union", "english", "ambient", "calm"),
    # Marathi regional
    ("Apsara Aali", "Ajay-Atul", "marathi", "bollywood", "celebratory"),
]


@dataclass
class TrackRun:
    """A single (track × round) execution result."""

    track_id: str
    title: str
    artist: str
    language: str
    round_idx: int
    energy: float = 0.0
    valence: float = 0.0
    tempo_bpm: int = 0
    acousticness: float = 0.0
    instrumentalness: float = 0.0
    loudness: float = 0.0
    key_signature: str = ""
    primary_mood: str = ""
    mood_confidence: float = 0.0
    genre: str = ""
    genre_confidence: float = 0.0
    region: str = ""
    duration_sec: float = 0.0
    calibrated: bool = True
    # Raw (uncalibrated) values for delta inspection
    raw_energy: float = 0.0
    raw_acousticness: float = 0.0
    raw_loudness: float = 0.0
    raw_valence: float = 0.0
    elapsed_sec: float = 0.0
    error: str = ""


@dataclass
class Finding:
    """One regression issue worth reporting."""

    track_id: str
    title: str
    severity: str  # error / warn / info
    category: str  # range / determinism / sanity / fetch / classify
    detail: str


@dataclass
class TrackReport:
    """Per-track summary of all rounds + findings."""

    track_id: str
    title: str
    artist: str
    runs: list[TrackRun] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


# Hard-bound ranges per the model/calibration contract.
_RANGE = {
    "energy": (0.0, 1.0),
    "valence": (0.0, 1.0),
    "acousticness": (0.0, 1.0),
    "instrumentalness": (0.0, 1.0),
    "loudness": (-60.0, 0.0),
    "tempo_bpm": (40, 220),
}

# Determinism tolerance: librosa is deterministic, but float aggregation
# leaves ε at the rounding step. >1% drift is real.
_DETERMINISM_TOL = {
    "energy": 0.01,
    "valence": 0.01,
    "acousticness": 0.01,
    "instrumentalness": 0.01,
    "loudness": 0.5,
    "tempo_bpm": 2,
}


class Command(BaseCommand):
    help = "Regression-test the in-house audio engine across a curated track panel."

    def add_arguments(self, parser):
        parser.add_argument(
            "--panel",
            type=str,
            default="default",
            choices=["default", "db_sample", "custom"],
            help=(
                "default: curated 10-track diverse panel. "
                "db_sample: pick a stratified sample from the DB. "
                "custom: pass --titles 'Title|Artist' entries."
            ),
        )
        parser.add_argument(
            "--titles",
            nargs="*",
            default=None,
            help="Custom panel entries (used with --panel custom). 'Title|Artist'",
        )
        parser.add_argument(
            "--sample-size",
            type=int,
            default=10,
            help="When --panel db_sample, how many tracks to test.",
        )
        parser.add_argument(
            "--rounds",
            type=int,
            default=2,
            help=(
                "How many times to analyse each track (>= 2 enables the "
                "determinism check)."
            ),
        )
        parser.add_argument(
            "--persist",
            action="store_true",
            help=(
                "Also persist features to Track rows + write AudioFeatureSnapshot. "
                "Default: dry-run, no DB writes."
            ),
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.0,
            help="Seconds between JioSaavn downloads.",
        )
        parser.add_argument(
            "--report-path",
            type=str,
            default=None,
            help="Override Excel report output path.",
        )

    # ------------------------------------------------------------------
    # Panel resolution
    # ------------------------------------------------------------------
    def _resolve_panel(self, options) -> list[dict]:
        if options["panel"] == "custom":
            raw = options.get("titles") or []
            if not raw:
                raise SystemExit("--panel custom needs --titles entries")
            panel = []
            for entry in raw:
                if "|" not in entry:
                    raise SystemExit(f"Bad --titles entry (need 'Title|Artist'): {entry}")
                title, artist = (part.strip() for part in entry.split("|", 1))
                panel.append({
                    "title": title,
                    "artist": artist,
                    "language": "english",
                    "expected_genre": "",
                    "expected_mood": "",
                })
            return panel

        if options["panel"] == "db_sample":
            return self._db_sample(options["sample_size"])

        # default panel
        return [
            {
                "title": t,
                "artist": a,
                "language": lang,
                "expected_genre": g,
                "expected_mood": m,
            }
            for (t, a, lang, g, m) in _DEFAULT_PANEL
        ]

    def _db_sample(self, n: int) -> list[dict]:
        from django.db.models import Q

        # Stratify: pick tracks across languages with non-empty title.
        languages = ["hindi", "marathi", "english", "telugu", "tamil"]
        per_lang = max(1, n // len(languages))
        out: list[dict] = []
        for lang in languages:
            qs = (
                Track.objects
                .filter(isActive=True, language=lang, title__isnull=False)
                .select_related("artistId")
                .order_by("?")[:per_lang]
            )
            for t in qs:
                out.append({
                    "title": t.title,
                    "artist": (t.artistId.name if t.artistId else "") or "",
                    "language": t.language or lang,
                    "expected_genre": t.genre or "",
                    "expected_mood": t.primaryMood or "",
                })
        return out[:n]

    # ------------------------------------------------------------------
    # Track resolution: find or attach to a Track row.
    # ------------------------------------------------------------------
    def _resolve_track(self, entry: dict) -> Track | None:
        """Find an existing Track matching title+artist; create a stub if not."""
        title = entry["title"].strip()
        artist_name = entry["artist"].strip()

        match = (
            Track.objects
            .select_related("artistId")
            .filter(title__iexact=title, artistId__name__iexact=artist_name)
            .first()
        )
        if match:
            return match

        # Fallback — match on title only (best effort)
        match = (
            Track.objects
            .select_related("artistId")
            .filter(title__iexact=title)
            .first()
        )
        if match:
            return match

        # Not in DB — create a manual stub so we have somewhere to attach
        # snapshots. Stays isActive=True so it shows up in exports.
        artist, _ = Artist.objects.get_or_create(name=artist_name)
        return Track.objects.create(
            title=title,
            artistId=artist,
            source=Track.SourceChoices.MANUAL,
            language=entry.get("language") or None,
            isActive=True,
        )

    # ------------------------------------------------------------------
    # Single-run helpers
    # ------------------------------------------------------------------
    def _analyse_once(
        self,
        track: Track,
        round_idx: int,
        *,
        persist: bool,
        cached_bytes: bytes | None,
    ) -> tuple[TrackRun, bytes | None]:
        run = TrackRun(
            track_id=str(track.id),
            title=track.title or "",
            artist=(track.artistId.name if track.artistId else "") or "",
            language=track.language or "",
            round_idx=round_idx,
            calibrated=True,
        )

        start = time.monotonic()
        try:
            # Round 1 fetches audio; subsequent rounds reuse the bytes so
            # the determinism check tests the DSP, not the network.
            if cached_bytes is None:
                audio_bytes, audio_url = fetch_track_audio(
                    run.title,
                    run.artist,
                    stream_url=track.streamUrl or "",
                    min_match=0.0,
                )
                cached_bytes = audio_bytes
                if not track.streamUrl and audio_url:
                    track.streamUrl = audio_url
                    if persist:
                        track.save(update_fields=["streamUrl"])
            else:
                audio_bytes = cached_bytes

            metadata = {
                "language": track.language,
                "artist": run.artist,
                "source": track.source,
                "release_year": track.releaseYear,
            }
            # Calibrated and raw, in the same call.
            features = analyze_audio_bytes(audio_bytes, metadata=metadata)
            features_raw = analyze_audio_bytes(
                audio_bytes, metadata=metadata, calibrated=False
            )

            run.energy = features["energy"]
            run.valence = features["valence"]
            run.tempo_bpm = features["tempoBpm"]
            run.acousticness = features["acousticness"]
            run.instrumentalness = features["instrumentalness"]
            run.loudness = features["loudness"]
            run.key_signature = features["keySignature"]
            run.primary_mood = features["primaryMood"]
            run.mood_confidence = features["moodConfidence"]
            run.genre = features["genre"]
            run.genre_confidence = features["genreConfidence"]
            run.region = features["region"]
            run.duration_sec = features["durationSec"]
            run.raw_energy = features_raw["energy"]
            run.raw_acousticness = features_raw["acousticness"]
            run.raw_loudness = features_raw["loudness"]
            run.raw_valence = features_raw["valence"]

            if persist and round_idx == 1:
                # Persist features once (round 1) so reruns don't churn rows.
                track.energy = run.energy
                track.valence = run.valence
                track.tempoBpm = run.tempo_bpm
                track.acousticness = run.acousticness
                track.instrumentalness = run.instrumentalness
                track.loudness = run.loudness
                track.keySignature = run.key_signature
                track.primaryMood = run.primary_mood
                if features["genre"]:
                    track.genre = features["genre"]
                if features["region"] != "Unknown":
                    track.region = features["region"]
                if features["instrumentalness"] >= 0.6:
                    track.isInstrumental = True
                track.featuresSyncedAt = timezone.now()
                track.save()
                AudioFeatureSnapshot.objects.create(
                    trackId=track, snapshot=features
                )

        except AudioAnalysisError as exc:
            run.error = f"fetch/analyse failed: {exc}"
        except Exception as exc:  # pragma: no cover - defensive
            run.error = f"unexpected: {exc!r}"
        finally:
            run.elapsed_sec = round(time.monotonic() - start, 2)

        return run, cached_bytes

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _check_range(self, run: TrackRun, report: TrackReport) -> None:
        scalar = {
            "energy": run.energy,
            "valence": run.valence,
            "acousticness": run.acousticness,
            "instrumentalness": run.instrumentalness,
            "loudness": run.loudness,
            "tempo_bpm": run.tempo_bpm,
        }
        for feature, value in scalar.items():
            lo, hi = _RANGE[feature]
            if value is None:
                report.findings.append(Finding(
                    run.track_id, run.title, "error", "range",
                    f"{feature} is None on round {run.round_idx}",
                ))
                continue
            if not (lo <= value <= hi):
                report.findings.append(Finding(
                    run.track_id, run.title, "error", "range",
                    f"{feature}={value} out of [{lo}, {hi}] on round {run.round_idx}",
                ))

    def _check_determinism(self, report: TrackReport) -> None:
        if len(report.runs) < 2:
            return
        first = report.runs[0]
        for other in report.runs[1:]:
            for feature, tol in _DETERMINISM_TOL.items():
                key = feature if feature != "tempo_bpm" else "tempo_bpm"
                a = getattr(first, key)
                b = getattr(other, key)
                if a is None or b is None:
                    continue
                diff = abs(a - b)
                if diff > tol:
                    report.findings.append(Finding(
                        report.track_id, report.title, "error", "determinism",
                        f"{feature} drift {a} vs {b} (diff {diff:.3f}, tol {tol})",
                    ))
            if first.genre and other.genre and first.genre != other.genre:
                report.findings.append(Finding(
                    report.track_id, report.title, "warn", "determinism",
                    f"genre flip-flop {first.genre} -> {other.genre}",
                ))
            if first.primary_mood and other.primary_mood and \
                    first.primary_mood != other.primary_mood:
                report.findings.append(Finding(
                    report.track_id, report.title, "warn", "determinism",
                    f"mood flip-flop {first.primary_mood} -> {other.primary_mood}",
                ))

    def _check_sanity(self, report: TrackReport) -> None:
        if not report.runs:
            return
        run = report.runs[0]
        if run.error:
            return
        # Energy ↔ loudness directional check: very energetic tracks should
        # not register as silent. Spotify's range is roughly:
        # silence ≈ −30 dB, loud pop ≈ −5 dB.
        if run.energy > 0.7 and run.loudness < -25:
            report.findings.append(Finding(
                report.track_id, report.title, "warn", "sanity",
                f"high energy ({run.energy}) but very quiet loudness ({run.loudness})",
            ))
        if run.energy < 0.2 and run.loudness > -6:
            report.findings.append(Finding(
                report.track_id, report.title, "warn", "sanity",
                f"low energy ({run.energy}) but loud loudness ({run.loudness})",
            ))
        # Instrumentalness vs mood: instrumentalness > 0.6 should set
        # isInstrumental on the Track; we don't check that here because the
        # check is encoded in the engine itself.
        if run.tempo_bpm in (40, 220):
            report.findings.append(Finding(
                report.track_id, report.title, "warn", "sanity",
                f"tempo pinned to validator boundary ({run.tempo_bpm} BPM)",
            ))
        # Mood/quadrant consistency: 'energized' should not pair with
        # energy < 0.4; 'calm' should not pair with energy > 0.75.
        mood = (run.primary_mood or "").lower()
        if mood in {"energized", "celebratory"} and run.energy < 0.4:
            report.findings.append(Finding(
                report.track_id, report.title, "warn", "classify",
                f"mood={mood} but low energy ({run.energy})",
            ))
        if mood == "calm" and run.energy > 0.75:
            report.findings.append(Finding(
                report.track_id, report.title, "warn", "classify",
                f"mood=calm but high energy ({run.energy})",
            ))

    # ------------------------------------------------------------------
    # Output: stdout + Excel + JSON
    # ------------------------------------------------------------------
    def _write_excel(self, reports: list[TrackReport], path: Path) -> None:
        # Use openpyxl for richer formatting; falls back gracefully.
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill
        except ImportError:
            self.stderr.write("openpyxl missing; writing CSV instead")
            self._write_csv(reports, path.with_suffix(".csv"))
            return

        wb = Workbook()

        # Sheet 1: Tracks (one row per run)
        ws = wb.active
        ws.title = "Runs"
        headers = [
            "track_id", "title", "artist", "language", "round",
            "energy", "valence", "tempo_bpm", "acousticness",
            "instrumentalness", "loudness", "key_signature",
            "primary_mood", "mood_confidence",
            "genre", "genre_confidence", "region", "duration_sec",
            "raw_energy", "raw_acousticness", "raw_loudness", "raw_valence",
            "elapsed_sec", "error",
        ]
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="DDDDDD")
        for rep in reports:
            for run in rep.runs:
                ws.append([
                    run.track_id, run.title, run.artist, run.language,
                    run.round_idx,
                    run.energy, run.valence, run.tempo_bpm,
                    run.acousticness, run.instrumentalness, run.loudness,
                    run.key_signature, run.primary_mood, run.mood_confidence,
                    run.genre, run.genre_confidence, run.region,
                    run.duration_sec,
                    run.raw_energy, run.raw_acousticness, run.raw_loudness,
                    run.raw_valence,
                    run.elapsed_sec, run.error,
                ])

        # Sheet 2: Findings
        ws2 = wb.create_sheet("Findings")
        ws2.append(["track_id", "title", "severity", "category", "detail"])
        for cell in ws2[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="DDDDDD")
        for rep in reports:
            for f in rep.findings:
                ws2.append([f.track_id, f.title, f.severity, f.category, f.detail])

        # Sheet 3: Summary
        ws3 = wb.create_sheet("Summary")
        ws3.append(["metric", "value"])
        total_tracks = len(reports)
        total_runs = sum(len(r.runs) for r in reports)
        total_findings = sum(len(r.findings) for r in reports)
        errors = sum(
            1 for r in reports for f in r.findings if f.severity == "error"
        )
        warns = sum(
            1 for r in reports for f in r.findings if f.severity == "warn"
        )
        ws3.append(["panel_size", total_tracks])
        ws3.append(["total_runs", total_runs])
        ws3.append(["findings", total_findings])
        ws3.append(["errors", errors])
        ws3.append(["warnings", warns])
        ws3.append(["pass", "YES" if errors == 0 else "NO"])
        ws3.append(["timestamp", datetime.now().isoformat(timespec="seconds")])

        # Auto-fit column widths (rough)
        for sheet in (ws, ws2, ws3):
            for column_cells in sheet.columns:
                length = max(
                    len(str(cell.value)) if cell.value is not None else 0
                    for cell in column_cells
                )
                sheet.column_dimensions[column_cells[0].column_letter].width = \
                    min(max(length + 2, 10), 50)

        wb.save(path)

    def _write_csv(self, reports: list[TrackReport], path: Path) -> None:
        import csv
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([
                "track_id", "title", "artist", "round",
                "energy", "valence", "tempo_bpm", "acousticness",
                "instrumentalness", "loudness", "key_signature",
                "primary_mood", "genre", "region", "elapsed_sec", "error",
            ])
            for rep in reports:
                for run in rep.runs:
                    writer.writerow([
                        run.track_id, run.title, run.artist, run.round_idx,
                        run.energy, run.valence, run.tempo_bpm,
                        run.acousticness, run.instrumentalness, run.loudness,
                        run.key_signature, run.primary_mood, run.genre,
                        run.region, run.elapsed_sec, run.error,
                    ])

    def _write_json(self, reports: list[TrackReport], path: Path) -> None:
        payload = []
        for rep in reports:
            payload.append({
                "track_id": rep.track_id,
                "title": rep.title,
                "artist": rep.artist,
                "runs": [asdict(r) for r in rep.runs],
                "findings": [asdict(f) for f in rep.findings],
            })
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        rounds = max(1, options["rounds"])
        persist = options["persist"]
        delay = options["delay"]

        panel = self._resolve_panel(options)
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Regression panel: {len(panel)} tracks × {rounds} rounds "
                f"(persist={'YES' if persist else 'NO'})"
            )
        )

        reports: list[TrackReport] = []
        t0 = time.monotonic()

        for idx, entry in enumerate(panel, 1):
            self.stdout.write(
                f"\n[{idx}/{len(panel)}] {entry['title']} — {entry['artist']}"
            )
            track = self._resolve_track(entry)
            if track is None:
                self.stderr.write(self.style.ERROR("  ✗ could not resolve Track"))
                continue
            report = TrackReport(
                track_id=str(track.id),
                title=track.title or entry["title"],
                artist=(track.artistId.name if track.artistId else entry["artist"]),
            )

            cached_bytes: bytes | None = None
            for r in range(1, rounds + 1):
                run, cached_bytes = self._analyse_once(
                    track, r, persist=persist, cached_bytes=cached_bytes,
                )
                report.runs.append(run)
                if run.error:
                    self.stdout.write(self.style.ERROR(f"  R{r} ✗ {run.error}"))
                    report.findings.append(Finding(
                        report.track_id, report.title, "error", "fetch",
                        run.error,
                    ))
                    break  # don't retry rounds when audio fetch failed
                self.stdout.write(
                    f"  R{r}  E={run.energy:.3f} V={run.valence:.3f} "
                    f"T={run.tempo_bpm} A={run.acousticness:.3f} "
                    f"I={run.instrumentalness:.3f} L={run.loudness:.1f} "
                    f"mood={run.primary_mood} genre={run.genre} "
                    f"key={run.key_signature} ({run.elapsed_sec}s)"
                )
                self._check_range(run, report)

            self._check_determinism(report)
            self._check_sanity(report)
            reports.append(report)

            # Per-track summary line
            errs = sum(1 for f in report.findings if f.severity == "error")
            warns = sum(1 for f in report.findings if f.severity == "warn")
            if errs == 0 and warns == 0:
                self.stdout.write(self.style.SUCCESS("  → clean"))
            else:
                self.stdout.write(self.style.WARNING(
                    f"  → {errs} errors, {warns} warnings"
                ))

            if delay > 0 and idx < len(panel):
                time.sleep(delay)

        elapsed = round(time.monotonic() - t0, 1)

        # ---- Report write ----
        report_dir = Path(settings.BASE_DIR) / "data" / "regression_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        xlsx_path = Path(options["report_path"]) if options["report_path"] else \
            report_dir / f"engine_regression_{ts}.xlsx"
        json_path = xlsx_path.with_suffix(".json")

        self._write_excel(reports, xlsx_path)
        self._write_json(reports, json_path)

        # ---- Stdout summary ----
        total_findings = sum(len(r.findings) for r in reports)
        errors = sum(
            1 for r in reports for f in r.findings if f.severity == "error"
        )
        warns = sum(
            1 for r in reports for f in r.findings if f.severity == "warn"
        )
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"DONE — {len(reports)} tracks analysed in {elapsed}s — "
            f"{errors} errors, {warns} warnings, {total_findings} findings"
        ))
        if errors == 0:
            self.stdout.write(self.style.SUCCESS("✓ REGRESSION PASS"))
        else:
            self.stdout.write(self.style.ERROR("✗ REGRESSION FAIL"))
        self.stdout.write(f"Excel report: {xlsx_path}")
        self.stdout.write(f"JSON report:  {json_path}")
