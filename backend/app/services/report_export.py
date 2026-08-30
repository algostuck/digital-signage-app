"""Report export engine (P2-RPT-004): CSV and XLSX for every operational
report, streamed with a proper filename. XLSX is generated dependency-free
(a minimal OOXML package with inline strings); PDF is deliberately out of
scope for this phase (documented deviation from the CSV/XLSX/PDF wish).
"""

import csv
import datetime as dt
import io
import uuid
import zipfile
from xml.sax.saxutils import escape

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationAppError
from app.services import reports

EXPORT_FORMATS = ("csv", "xlsx")

REPORTS = {
    "proof-of-play": "Proof of play",
    "campaign-performance": "Campaign performance",
    "device-uptime": "Device uptime",
    "deployments": "Campaign deployments",
    "playback": "Asset playback",
    "locations": "Location health",
    "audit": "Audit trail",  # additionally requires audit.view (P2-22)
}


def _parse_date(value, field: str) -> dt.date | None:
    if value in (None, ""):
        return None
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValidationAppError(f"{field} must be an ISO date", field=field) from exc


def _parse_uuid(value, field: str) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise ValidationAppError(f"{field} must be a UUID", field=field) from exc


async def run_report(
    db: AsyncSession, organization_id: uuid.UUID, report: str, filters: dict
) -> list[dict]:
    """Shared by the export endpoint and the JSON report endpoints."""
    if report not in REPORTS:
        raise ValidationAppError(
            f"report must be one of {sorted(REPORTS)}", field="report"
        )
    date_from = _parse_date(filters.get("date_from"), "date_from")
    date_to = _parse_date(filters.get("date_to"), "date_to")
    if report == "proof-of-play":
        return await reports.proof_of_play(
            db,
            organization_id,
            date_from=date_from,
            date_to=date_to,
            group_by=filters.get("group_by") or "campaign",
            campaign_id=_parse_uuid(filters.get("campaign_id"), "campaign_id"),
            location_id=_parse_uuid(filters.get("location_id"), "location_id"),
        )
    if report == "campaign-performance":
        return await reports.campaign_performance(
            db, organization_id, date_from=date_from, date_to=date_to
        )
    if report == "device-uptime":
        today = dt.date.today()
        return await reports.device_uptime(
            db,
            organization_id,
            date_from=date_from or today - dt.timedelta(days=7),
            date_to=date_to or today,
        )
    if report == "audit":
        from app.services import audit as audit_service

        rows, _total = await audit_service.search(
            db,
            organization_id,
            action=filters.get("action") or None,
            entity_type=filters.get("entity_type") or None,
            user_id=_parse_uuid(filters.get("user_id"), "user_id"),
            date_from=date_from,
            date_to=date_to,
            page=1,
            page_size=10_000,
        )
        import json

        return [
            {
                "created_at": row.created_at.isoformat(),
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "user_id": str(row.user_id) if row.user_id else None,
                "ip_address": row.ip_address,
                "request_id": row.request_id,
                "after": json.dumps(row.after_json) if row.after_json else None,
            }
            for row in rows
        ]
    if report == "deployments":
        return await reports.deployments_report(db, organization_id)
    if report == "playback":
        return await reports.playback_report(
            db, organization_id, date_from=date_from, date_to=date_to
        )
    return await reports.locations_report(db, organization_id)


def to_csv(rows: list[dict]) -> bytes:
    buffer = io.StringIO(newline="")
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")  # BOM: Excel-friendly UTF-8


_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType='
    '"application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType='
    '"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    '<Override PartName="/xl/worksheets/sheet1.xml" ContentType='
    '"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    "</Types>"
)
_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
    '2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
    "</Relationships>"
)
_WORKBOOK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<sheets><sheet name="Report" sheetId="1" r:id="rId1"/></sheets></workbook>'
)
_WORKBOOK_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
    '2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
    "</Relationships>"
)


def _cell(value) -> str:
    if value is None:
        return "<c/>"
    if isinstance(value, bool):
        return f'<c t="inlineStr"><is><t>{value}</t></is></c>'
    if isinstance(value, int | float):
        return f"<c><v>{value}</v></c>"
    return f'<c t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'


def to_xlsx(rows: list[dict]) -> bytes:
    header = list(rows[0].keys()) if rows else []
    sheet_rows = ["<row>" + "".join(_cell(h) for h in header) + "</row>"]
    for row in rows:
        sheet_rows.append(
            "<row>" + "".join(_cell(row.get(h)) for h in header) + "</row>"
        )
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _ROOT_RELS)
        archive.writestr("xl/workbook.xml", _WORKBOOK)
        archive.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()


def render(rows: list[dict], format: str) -> tuple[bytes, str]:
    """Returns (content, media_type)."""
    if format == "csv":
        return to_csv(rows), "text/csv; charset=utf-8"
    if format == "xlsx":
        return (
            to_xlsx(rows),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    raise ValidationAppError(f"format must be one of {EXPORT_FORMATS}", field="format")
