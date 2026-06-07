"""Build the audio engine's training dataset.

Two phases, each writing one JSON line per analysed song:

  • ``valence.jsonl`` — top-popularity songs of one Indian language
    (default Hindi), with the CSV's ``Valence`` column as the target.

  • ``genre.jsonl`` — songs from ``data/spotify_dataset.csv``, balanced
    across the engine's broad buckets (electronic / rock / pop / hiphop /
    classical / acoustic / ambient). bollywood / ghazal / lofi are handled
    by the runtime overlay, not by the model itself.

Each row::

    {"features": {<50 flat features>}, "valence": 0.31,
     "title": "...", "artist": "..."}

JioSaavn name-search is gated by ``--min-match`` so wrong/alternate
recordings are skipped rather than poisoning the dataset. A feature-signal
probe is printed at the end of each phase — Pearson r against valence,
ANOVA F against genre — so we know whether the signal is even learnable
before spending time training.

Usage (inside Docker):
    docker compose run --rm --no-deps web python manage.py build_training_dataset
        --valence-samples 75
        --genre-samples-per-bucket 10
        --min-match 0.6
        --delay 0.5
        --language hindi
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

from django.core.management.base import BaseCommand

from tracks.analysis.audio_source import AudioAnalysisError, fetch_track_audio
from tracks.analysis.engine import analyze_audio_bytes
from tracks.analysis.training import (
    DATASET_DIR,
    GENRE_BUCKETS,
    bucket_for_genre,
    feature_dict_from_result,
    save_jsonl,
    signal_probe_classification,
    signal_probe_regression,
)

# Sample more than we need per bucket — Western tracks in spotify_dataset
# often miss on JioSaavn, so we over-request and stop when we hit the
# success quota.
_GENRE_OVER_REQUEST = 4
_VALENCE_OVER_REQUEST = 2


class Command(BaseCommand):
    help = "Collect (FeatureVector, label) rows for the valence + genre models."

    def add_arguments(self, parser):
        parser.add_argument("--valence-samples", type=int, default=75,
                            help="Target number of valence rows (default: 75)")
        parser.add_argument("--genre-samples-per-bucket", type=int, default=10,
                            help="Target rows per genre bucket (default: 10)")
        parser.add_argument("--min-match", type=float, default=0.6,
                            help="JioSaavn match-confidence gate, 0-1 (default: 0.6)")
        parser.add_argument("--delay", type=float, default=0.5,
                            help="Seconds between downloads (default: 0.5)")
        parser.add_argument("--language", type=str, default="hindi",
                            help="Language for the valence phase (default: hindi)")
        parser.add_argument("--valence-source", type=str, default="indian",
                            choices=["indian", "spotify"],
                            help="Where valence labels come from (default: indian)")
        parser.add_argument("--skip-valence", action="store_true")
        parser.add_argument("--skip-genre", action="store_true")

    # ------------------------------------------------------------------
    def handle(self, *args, **opt):
        DATASET_DIR.mkdir(parents=True, exist_ok=True)
        data_dir = Path(__file__).resolve().parents[3] / "data"

        if not opt["skip_valence"]:
            if opt["valence_source"] == "spotify":
                self._build_valence_spotify(
                    data_dir, target=opt["valence_samples"],
                    delay=opt["delay"], min_match=opt["min_match"],
                )
            else:
                self._build_valence(
                    data_dir, language=opt["language"].lower(),
                    target=opt["valence_samples"], delay=opt["delay"],
                    min_match=opt["min_match"],
                )

        if not opt["skip_genre"]:
            self._build_genre(
                data_dir,
                per_bucket=opt["genre_samples_per_bucket"],
                delay=opt["delay"], min_match=opt["min_match"],
            )

        self.stdout.write(self.style.SUCCESS("\n✓ Dataset build complete."))

    # ------------------------------------------------------------------
    # Phase 1 — valence
    # ------------------------------------------------------------------
    def _build_valence(self, data_dir, *, language, target, delay, min_match):
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n=== Valence dataset — top {target} popular '{language}' songs ==="
        ))
        candidates = self._popular_songs(data_dir, language, target * _VALENCE_OVER_REQUEST)
        if not candidates:
            self.stderr.write(self.style.ERROR(
                f"No '{language}' rows with Valence found — skipping valence phase."
            ))
            return

        rows: list[dict] = []
        for i, song in enumerate(candidates, 1):
            if len(rows) >= target:
                break
            ok = self._analyse_one(
                title=song["song_name"], artist=song["singer"],
                min_match=min_match, prefix=f"[v {len(rows) + 1}/{target}]",
            )
            if ok is None:
                pass
            else:
                rows.append({
                    "title": song["song_name"], "artist": song["singer"],
                    "language": language, "valence": song["valence"],
                    "features": ok,
                })
            if i < len(candidates) and delay > 0:
                time.sleep(delay)

        path = DATASET_DIR / "valence.jsonl"
        save_jsonl(rows, path)
        self.stdout.write(self.style.SUCCESS(
            f"  ✓ Wrote {len(rows)} valence rows -> {path.name}"
        ))

        # Signal probe
        probe = signal_probe_regression(rows, target_key="valence")
        self._print_probe("Valence signal probe (top |r|):", probe, top=10)

    # ------------------------------------------------------------------
    # Phase 1b — valence from spotify_dataset.csv (stratified across 0-1)
    # ------------------------------------------------------------------
    def _build_valence_spotify(self, data_dir, *, target, delay, min_match):
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n=== Valence dataset — {target} songs from spotify_dataset.csv "
            f"(stratified across the full 0-1 valence range) ==="
        ))
        candidates = self._stratified_spotify_candidates(
            data_dir, total_target=target * _VALENCE_OVER_REQUEST, bins=10,
        )
        if not candidates:
            self.stderr.write(self.style.ERROR(
                "No spotify_dataset.csv candidates — skipping valence phase."
            ))
            return

        rows: list[dict] = []
        for i, song in enumerate(candidates, 1):
            if len(rows) >= target:
                break
            ok = self._analyse_one(
                title=song["song_name"], artist=song["singer"],
                min_match=min_match,
                prefix=f"[v {len(rows) + 1}/{target}]",
            )
            if ok is not None:
                rows.append({
                    "title": song["song_name"], "artist": song["singer"],
                    "source": "spotify", "valence": song["valence"],
                    "features": ok,
                })
            if i < len(candidates) and delay > 0:
                time.sleep(delay)

        path = DATASET_DIR / "valence.jsonl"
        save_jsonl(rows, path)
        self.stdout.write(self.style.SUCCESS(
            f"  ✓ Wrote {len(rows)} valence rows -> {path.name}"
        ))
        probe = signal_probe_regression(rows, target_key="valence")
        self._print_probe("Valence signal probe (top |r|):", probe, top=10)

    # ------------------------------------------------------------------
    # Phase 2 — genre
    # ------------------------------------------------------------------
    def _build_genre(self, data_dir, *, per_bucket, delay, min_match):
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n=== Genre dataset — {per_bucket} per bucket "
            f"({len(GENRE_BUCKETS)} buckets) ==="
        ))
        candidates_by_bucket = self._spotify_candidates(
            data_dir, per_bucket * _GENRE_OVER_REQUEST,
        )

        rows: list[dict] = []
        for bucket in GENRE_BUCKETS:
            collected = 0
            self.stdout.write(self.style.HTTP_INFO(
                f"\n— Bucket: {bucket} —"
            ))
            for song in candidates_by_bucket.get(bucket, []):
                if collected >= per_bucket:
                    break
                ok = self._analyse_one(
                    title=song["track_name"], artist=song["artist"],
                    min_match=min_match,
                    prefix=f"[g {len(rows) + 1}] {bucket}",
                )
                if ok is not None:
                    rows.append({
                        "title": song["track_name"], "artist": song["artist"],
                        "spotify_genre": song["spotify_genre"],
                        "genre": bucket, "features": ok,
                    })
                    collected += 1
                if delay > 0:
                    time.sleep(delay)
            self.stdout.write(f"  bucket '{bucket}': {collected} collected")

        path = DATASET_DIR / "genre.jsonl"
        save_jsonl(rows, path)
        self.stdout.write(self.style.SUCCESS(
            f"\n  ✓ Wrote {len(rows)} genre rows -> {path.name}"
        ))

        probe = signal_probe_classification(rows, target_key="genre")
        self._print_probe("Genre signal probe (top ANOVA F):", probe, top=10)

    # ------------------------------------------------------------------
    # Shared
    # ------------------------------------------------------------------
    def _analyse_one(self, *, title, artist, min_match, prefix) -> dict | None:
        self.stdout.write(f"{prefix} {title} — {artist}")
        try:
            audio_bytes, _ = fetch_track_audio(title, artist, min_match=min_match)
            result = analyze_audio_bytes(audio_bytes, calibrated=False)
        except AudioAnalysisError as exc:
            self.stdout.write(self.style.WARNING(f"    skipped — {exc}"))
            return None
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.WARNING(f"    failed — {exc}"))
            return None
        return feature_dict_from_result(result)

    def _print_probe(self, header, probe, *, top):
        if not probe:
            self.stdout.write(f"\n{header} (no data)")
            return
        self.stdout.write(f"\n{header}")
        for name, value in probe[:top]:
            self.stdout.write(f"    {name:<22} {value:+.3f}")

    # ------------------------------------------------------------------
    # CSV loaders
    # ------------------------------------------------------------------
    def _popular_songs(self, data_dir: Path, language: str, max_candidates: int):
        pool: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for path in sorted(data_dir.glob("*_songs.csv")):
            with open(path, encoding="utf-8", errors="ignore", newline="") as fh:
                reader = csv.DictReader(fh)
                if not reader.fieldnames:
                    continue
                headers = {h.strip().lower(): h for h in reader.fieldnames if h}
                if "song_name" not in headers or "valence" not in headers:
                    continue
                for raw in reader:
                    lang = (raw.get(headers.get("language", "")) or "").strip().lower()
                    if lang != language:
                        continue
                    song = (raw.get(headers["song_name"]) or "").strip()
                    singer = (raw.get(headers.get("singer", "")) or "").strip().split("|")[0].strip()
                    if not song:
                        continue
                    key = (song.lower(), singer.lower())
                    if key in seen:
                        continue
                    valence = _to_float(raw.get(headers["valence"]))
                    popularity = _to_float(raw.get(headers.get("popularity", "")))
                    if valence is None:
                        continue
                    seen.add(key)
                    pool.append({"song_name": song, "singer": singer,
                                 "valence": valence,
                                 "popularity": popularity or 0.0})
        pool.sort(key=lambda r: r["popularity"], reverse=True)
        return pool[:max_candidates]

    def _stratified_spotify_candidates(self, data_dir: Path, *,
                                       total_target: int, bins: int = 10):
        """Sample spotify_dataset.csv evenly across the valence range.

        Each of ``bins`` valence strata contributes the most-popular songs,
        and we round-robin across strata so the final list interleaves the
        full happiness range — the data shape the regressor actually needs.
        """
        path = data_dir / "spotify_dataset.csv"
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"Missing {path}"))
            return []

        per_bin_cap = max(3, (total_target // bins) * 3)
        binned: list[list[dict]] = [[] for _ in range(bins)]
        seen: set[tuple[str, str]] = set()

        with open(path, encoding="utf-8", errors="ignore", newline="") as fh:
            reader = csv.DictReader(fh)
            headers = {h.strip().lower(): h for h in (reader.fieldnames or []) if h}
            need = {"track_name", "artists", "valence", "popularity"}
            if not need.issubset(headers):
                self.stderr.write(self.style.ERROR(
                    f"spotify_dataset.csv missing columns: {need - set(headers)}"
                ))
                return []
            for raw in reader:
                valence = _to_float(raw.get(headers["valence"]))
                if valence is None or not 0.0 <= valence <= 1.0:
                    continue
                bin_idx = min(bins - 1, int(valence * bins))
                if len(binned[bin_idx]) >= per_bin_cap:
                    continue
                name = (raw.get(headers["track_name"]) or "").strip()
                artists_raw = (raw.get(headers["artists"]) or "").strip()
                artist = artists_raw.split(";")[0].strip()
                if not name or not artist:
                    continue
                key = (name.lower(), artist.lower())
                if key in seen:
                    continue
                seen.add(key)
                popularity = _to_float(raw.get(headers["popularity"])) or 0.0
                binned[bin_idx].append({
                    "song_name": name, "singer": artist,
                    "valence": valence, "popularity": popularity,
                })

        for bucket in binned:
            bucket.sort(key=lambda r: r["popularity"], reverse=True)

        # Round-robin across bins so consecutive attempts span the full range.
        interleaved: list[dict] = []
        for round_idx in range(per_bin_cap):
            for bucket in binned:
                if round_idx < len(bucket):
                    interleaved.append(bucket[round_idx])
        return interleaved

    def _spotify_candidates(self, data_dir: Path, per_bucket_target: int):
        path = data_dir / "spotify_dataset.csv"
        if not path.exists():
            self.stderr.write(self.style.ERROR(
                f"Missing {path} — cannot build genre dataset."
            ))
            return {}

        buckets: dict[str, list[dict]] = {b: [] for b in GENRE_BUCKETS}
        seen: set[tuple[str, str]] = set()
        with open(path, encoding="utf-8", errors="ignore", newline="") as fh:
            reader = csv.DictReader(fh)
            headers = {h.strip().lower(): h for h in (reader.fieldnames or []) if h}
            need = {"track_name", "artists", "track_genre", "popularity"}
            if not need.issubset(headers):
                self.stderr.write(self.style.ERROR(
                    f"spotify_dataset.csv is missing required columns: "
                    f"{need - set(headers)}"
                ))
                return {}
            for raw in reader:
                bucket = bucket_for_genre(raw.get(headers["track_genre"], ""))
                if bucket is None:
                    continue
                if len(buckets[bucket]) >= per_bucket_target:
                    continue
                name = (raw.get(headers["track_name"]) or "").strip()
                artists_raw = (raw.get(headers["artists"]) or "").strip()
                artist = artists_raw.split(";")[0].strip()
                if not name or not artist:
                    continue
                key = (name.lower(), artist.lower())
                if key in seen:
                    continue
                seen.add(key)
                popularity = _to_float(raw.get(headers["popularity"])) or 0.0
                buckets[bucket].append({
                    "track_name": name, "artist": artist,
                    "spotify_genre": raw.get(headers["track_genre"], "").strip(),
                    "popularity": popularity,
                })

        for bucket in buckets:
            buckets[bucket].sort(key=lambda r: r["popularity"], reverse=True)
        return buckets


def _to_float(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None
