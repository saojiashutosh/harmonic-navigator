from __future__ import annotations

import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

from .models import Track


WORKSHEET_NAME = "Songs"

HEADERS = (
    "id",
    "title",
    "artist_name",
    "artist_spotify_id",
    "type",
    "source",
    "spotify_id",
    "fma_id",
    "preview_url",
    "external_url",
    "tempo_bpm",
    "duration_ms",
    "duration_minutes",
    "key_signature",
    "energy",
    "valence",
    "acousticness",
    "instrumentalness",
    "loudness",
    "primary_mood",
    "is_instrumental",
    "is_explicit",
    "is_active",
    "features_synced_at",
    "created_at",
    "updated_at",
    "excel_synced_at",
)


def sync_track_to_excel(track: Track) -> Path:
    """Refresh the single song-storage workbook after one track changes."""
    return export_tracks_to_excel()


def export_tracks_to_excel(tracks: QuerySet[Track] | None = None, path: str | os.PathLike | None = None) -> Path:
    workbook_path = Path(path or get_song_excel_backup_path())
    workbook_path.parent.mkdir(parents=True, exist_ok=True)

    rows = [_track_to_row(track) for track in _get_tracks(tracks)]
    _write_workbook(workbook_path, rows)
    return workbook_path


def get_song_excel_backup_path() -> Path:
    return Path(settings.SONG_EXCEL_BACKUP_PATH)


def _get_tracks(tracks: QuerySet[Track] | None) -> QuerySet[Track]:
    queryset = tracks if tracks is not None else Track.objects.all()
    return queryset.select_related("artistId").order_by("createdAt", "id")


def _track_to_row(track: Track) -> tuple:
    artist = track.artistId
    return (
        track.id,
        track.title,
        artist.name if artist else None,
        artist.spotifyId if artist else None,
        track.type,
        track.source,
        track.spotifyId,
        track.fmaId,
        track.previewUrl,
        track.externalUrl,
        track.tempoBpm,
        track.durationMs,
        track.duration_minutes,
        track.keySignature,
        track.energy,
        track.valence,
        track.acousticness,
        track.instrumentalness,
        track.loudness,
        track.primaryMood,
        track.isInstrumental,
        track.isExplicit,
        track.isActive,
        track.featuresSyncedAt,
        track.createdAt,
        track.updatedAt,
        timezone.now(),
    )


def _write_workbook(path: Path, rows: list[tuple]) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".xlsx", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with zipfile.ZipFile(tmp_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", _content_types_xml())
            archive.writestr("_rels/.rels", _root_relationships_xml())
            archive.writestr("xl/workbook.xml", _workbook_xml())
            archive.writestr("xl/_rels/workbook.xml.rels", _workbook_relationships_xml())
            archive.writestr("xl/styles.xml", _styles_xml())
            archive.writestr("xl/worksheets/sheet1.xml", _worksheet_xml(rows))
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _worksheet_xml(rows: list[tuple]) -> str:
    all_rows = [HEADERS, *rows]
    column_widths = _column_widths(all_rows)
    worksheet_rows = "\n".join(_row_xml(index, row) for index, row in enumerate(all_rows, start=1))
    columns = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(column_widths, start=1)
    )
    dimension = f"A1:{_column_name(len(HEADERS))}{len(all_rows)}"

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="{dimension}"/>'
        f"<cols>{columns}</cols>"
        "<sheetViews><sheetView workbookViewId=\"0\"><pane ySplit=\"1\" topLeftCell=\"A2\" "
        'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f"<sheetData>{worksheet_rows}</sheetData>"
        '<autoFilter ref="A1:AA1"/>'
        "</worksheet>"
    )


def _row_xml(row_index: int, row: tuple) -> str:
    cells = "".join(
        _cell_xml(row_index, column_index, value, is_header=row_index == 1)
        for column_index, value in enumerate(row, start=1)
    )
    return f'<row r="{row_index}">{cells}</row>'


def _cell_xml(row_index: int, column_index: int, value, is_header: bool = False) -> str:
    cell_ref = f"{_column_name(column_index)}{row_index}"
    style = ' s="1"' if is_header else ""

    if value is None:
        return f'<c r="{cell_ref}"{style}/>'
    if isinstance(value, bool):
        return f'<c r="{cell_ref}" t="b"{style}><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{cell_ref}"{style}><v>{value}</v></c>'

    text = _normalise_text(value)
    return f'<c r="{cell_ref}" t="inlineStr"{style}><is><t>{escape(text)}</t></is></c>'


def _normalise_text(value) -> str:
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.isoformat(timespec="seconds")
    return str(value)


def _column_widths(rows: list[tuple]) -> list[int]:
    widths = []
    for column_index in range(len(HEADERS)):
        max_length = max(len(_normalise_text(row[column_index])) if row[column_index] is not None else 0 for row in rows)
        widths.append(min(max(max_length + 2, 10), 60))
    return widths


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _content_types_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        "</Types>"
    )


def _root_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _workbook_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        f'<sheet name="{WORKSHEET_NAME}" sheetId="1" r:id="rId1"/>'
        "</sheets>"
        "</workbook>"
    )


def _workbook_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        "</Relationships>"
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<fonts count=\"2\"><font><sz val=\"11\"/><name val=\"Calibri\"/></font>"
        "<font><b/><sz val=\"11\"/><name val=\"Calibri\"/></font></fonts>"
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
        "</styleSheet>"
    )
