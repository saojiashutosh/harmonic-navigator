"""Load the entire Harmonic Navigator DB from an Excel workbook produced by
`export_db_to_excel.py`.

Idempotent: uses `update_or_create(pk=...)` so re-running on a populated DB
just refreshes rows in place. Designed so a new contributor can run

    docker compose up -d
    docker compose exec web python scripts/import_db_from_excel.py /app/data/full_db_export.xlsx

and end up with exactly the same data the workbook was exported from —
artists, tracks, users (with hashed passwords intact), playlists, group
sessions, feedback, the lot.

Notes:
  * UUID primary keys are preserved verbatim, so FK references resolve
    cleanly across sheets.
  * `auto_now` / `auto_now_add` fields are temporarily turned off during
    the import so original `created_at` / `updated_at` timestamps are kept.
  * Wrap the whole load in a single transaction so a mid-import failure
    rolls back instead of leaving the DB half-populated.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.development")

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.db import models as dj_models, transaction  # noqa: E402
from openpyxl import load_workbook  # noqa: E402


# Must mirror MODEL_ORDER in export_db_to_excel.py — parents before children.
MODEL_ORDER: list[tuple[str, str]] = [
    ("users", "Users"),
    ("users", "UsersDevices"),
    ("tracks", "Artist"),
    ("tracks", "MoodTag"),
    ("tracks", "Track"),
    ("tracks", "TrackMoodTag"),
    ("tracks", "AudioFeatureSnapshot"),
    ("moods", "Question"),
    ("moods", "MoodSession"),
    ("moods", "Answer"),
    ("moods", "MoodInference"),
    ("playlists", "Playlist"),
    ("playlists", "PlaylistTrack"),
    ("playlists", "SavedPlaylist"),
    ("groups", "GroupSession"),
    ("groups", "GroupParticipant"),
    ("feedback", "TrackFeedback"),
    ("feedback", "UserMoodPreference"),
    ("feedback", "TrackMoodScore"),
    ("music", "MusicTrack"),
]


def _sheet_name(app_label: str, model_name: str) -> str:
    return f"{app_label}.{model_name}"[:31]


def _is_empty(val) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    return False


def _to_datetime(raw):
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, date):
        return datetime(raw.year, raw.month, raw.day)
    s = str(raw).strip()
    # Postgres / Django sometimes emit "+00:00"; fromisoformat handles that
    # natively on Python 3.11+. Fall back to a Z->+00:00 swap.
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None


_STRING_FIELDS = (
    dj_models.CharField,
    dj_models.TextField,
    dj_models.EmailField,
    dj_models.URLField,
    dj_models.SlugField,
)


def _deserialize(field, raw):
    if _is_empty(raw):
        # For non-nullable string-ish columns, fall back to "" so we don't
        # trip NOT NULL constraints on rows that legitimately stored NULL in
        # the source DB (schema drift between the model and the live table).
        if isinstance(field, _STRING_FIELDS) and not field.null:
            return ""
        return None

    if isinstance(field, dj_models.UUIDField):
        if isinstance(raw, UUID):
            return raw
        return UUID(str(raw))

    if isinstance(field, dj_models.DateTimeField):
        return _to_datetime(raw)
    if isinstance(field, dj_models.DateField):
        dt = _to_datetime(raw)
        return dt.date() if dt else None

    if isinstance(field, dj_models.JSONField):
        if isinstance(raw, (dict, list)):
            return raw
        try:
            return json.loads(str(raw))
        except (json.JSONDecodeError, TypeError, ValueError):
            return raw

    if isinstance(field, dj_models.BooleanField):
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("true", "1", "yes", "t", "y")

    if isinstance(field, (
        dj_models.IntegerField,
        dj_models.BigIntegerField,
        dj_models.SmallIntegerField,
        dj_models.PositiveIntegerField,
        dj_models.PositiveSmallIntegerField,
        dj_models.PositiveBigIntegerField,
    )):
        try:
            # Excel sometimes round-trips ints as floats.
            return int(float(raw))
        except (ValueError, TypeError):
            return None

    if isinstance(field, dj_models.FloatField):
        try:
            return float(raw)
        except (ValueError, TypeError):
            return None

    # Catch-all: strings, CharField, TextField, EmailField, URLField, etc.
    return str(raw)


class _SuspendAutoTimestamps:
    """Temporarily disable auto_now / auto_now_add on a model's datetime fields
    so explicit values from the workbook are preserved on save."""

    def __init__(self, Model):
        self.Model = Model
        self._saved = []

    def __enter__(self):
        for f in self.Model._meta.fields:
            if isinstance(f, dj_models.DateTimeField) and (
                getattr(f, "auto_now", False) or getattr(f, "auto_now_add", False)
            ):
                self._saved.append((f, f.auto_now, f.auto_now_add))
                f.auto_now = False
                f.auto_now_add = False
        return self

    def __exit__(self, exc_type, exc, tb):
        for f, an, ana in self._saved:
            f.auto_now = an
            f.auto_now_add = ana


_BATCH_SIZE = 500


def _import_model(wb, app_label: str, model_name: str) -> tuple[int, int, int]:
    """Bulk-upsert one sheet into its Model.

    Uses Postgres `INSERT ... ON CONFLICT DO UPDATE` via `bulk_create(
    update_conflicts=True)` for speed — row-by-row `update_or_create` is
    too slow for thousands of rows (each row took ~3 round trips).
    """
    sheet = _sheet_name(app_label, model_name)
    if sheet not in wb.sheetnames:
        return (0, 0, 0)

    Model = apps.get_model(app_label, model_name)
    ws = wb[sheet]
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        return (0, 0, 0)

    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    field_by_attname = {f.attname: f for f in Model._meta.fields}
    # Fields we'll update on conflict (everything except the PK itself).
    update_attnames = [f.attname for f in Model._meta.fields if f.attname != "id"]

    # Figure out which PKs already exist so we can report new vs updated.
    existing_pks: set = set(Model.objects.values_list("pk", flat=True))

    instances = []
    skipped = 0
    seen_pks = set()
    with _SuspendAutoTimestamps(Model):
        for row in rows[1:]:
            if all(_is_empty(v) for v in row):
                continue

            kwargs = {}
            pk = None
            for header, raw in zip(headers, row):
                field = field_by_attname.get(header)
                if field is None:
                    continue
                value = _deserialize(field, raw)
                kwargs[header] = value
                if header == "id":
                    pk = value

            if pk is None:
                skipped += 1
                continue
            if pk in seen_pks:
                # Duplicate row in the sheet — keep the first one.
                skipped += 1
                continue
            seen_pks.add(pk)
            instances.append(Model(**kwargs))

        for start in range(0, len(instances), _BATCH_SIZE):
            batch = instances[start:start + _BATCH_SIZE]
            Model.objects.bulk_create(
                batch,
                update_conflicts=True,
                unique_fields=["id"],
                update_fields=update_attnames,
            )

    created = sum(1 for pk in seen_pks if pk not in existing_pks)
    updated = len(seen_pks) - created
    return (created, updated, skipped)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import the entire DB from an Excel workbook produced by export_db_to_excel.py",
    )
    parser.add_argument("input", help="Path to the .xlsx workbook")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Open and validate the workbook without writing anything.",
    )
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"ERROR: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    wb = load_workbook(args.input, read_only=False, data_only=True)

    if args.dry_run:
        print(f"DRY RUN — reading {args.input}")
        for app_label, model_name in MODEL_ORDER:
            sheet = _sheet_name(app_label, model_name)
            if sheet in wb.sheetnames:
                n = max(wb[sheet].max_row - 1, 0)
                print(f"  - {app_label}.{model_name}: {n} rows")
            else:
                print(f"  - {app_label}.{model_name}: (no sheet)")
        return

    print(f"Importing from {args.input}")
    total_c = total_u = total_s = 0
    with transaction.atomic():
        for app_label, model_name in MODEL_ORDER:
            try:
                apps.get_model(app_label, model_name)
            except LookupError:
                print(f"  - {app_label}.{model_name}: SKIPPED (model not found)")
                continue
            c, u, s = _import_model(wb, app_label, model_name)
            total_c += c
            total_u += u
            total_s += s
            print(f"  - {app_label}.{model_name}: +{c} new, ~{u} updated, !{s} skipped", flush=True)

    print(f"\nDone — {total_c} created, {total_u} updated, {total_s} skipped.")


if __name__ == "__main__":
    main()
