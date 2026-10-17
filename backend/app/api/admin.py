"""Admin and scheduled-job endpoints (Azure Functions timers call these). Require X-Admin-Token."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import select

from app.api.briefs import brief_out
from app.deps import AppSettings, DbSession, Gateway, require_admin
from app.models import FieldReport, Language, OutboxStatus, ReportStatus, User
from app.schemas import (
    BriefOut,
    BroadcastOut,
    ImportOut,
    RefreshOut,
    ReportOut,
    ReportStatusUpdate,
)
from app.services.briefs import generate_brief, latest_brief, render_brief
from app.services.importers import ImportResult, import_forecasts_csv, import_prices_csv
from app.services.reports import list_reports
from app.services.sms_gateway import deliver
from app.services.snapshot import refresh_snapshots

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def report_out(report: FieldReport) -> ReportOut:
    return ReportOut(
        id=report.id,
        client_ref=report.client_ref,
        reporter_phone=report.reporter_phone,
        channel=report.channel.value,
        crop_code=report.crop.code,
        market_code=report.market.code,
        grade=report.grade,
        price_ugx_per_kg=report.price_ugx_per_kg,
        reported_at=report.reported_at,
        received_at=report.received_at,
        status=report.status,
        deviation_pct=report.deviation_pct,
        note=report.note,
    )


async def _read_csv(file: UploadFile) -> str:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "CSV larger than 5 MB")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "CSV must be UTF-8") from exc


def _import_out(result: ImportResult) -> ImportOut:
    return ImportOut(created=result.created, updated=result.updated, errors=result.errors)


@router.post("/refresh", response_model=RefreshOut, summary="Recompute price snapshots (daily job)")
def refresh(db: DbSession, settings: AppSettings) -> RefreshOut:
    result = refresh_snapshots(db, settings)
    return RefreshOut(snapshots=result.snapshots, generated_at=result.generated_at)


@router.post("/prices/import", response_model=ImportOut, summary="Import observed prices CSV (data team)")
async def import_prices(file: UploadFile, db: DbSession, settings: AppSettings) -> ImportOut:
    return _import_out(import_prices_csv(db, await _read_csv(file), settings))


@router.post("/forecasts/import", response_model=ImportOut, summary="Import model forecasts CSV (model team)")
async def import_forecasts(file: UploadFile, db: DbSession) -> ImportOut:
    return _import_out(import_forecasts_csv(db, await _read_csv(file)))


@router.post("/briefs/generate", response_model=BriefOut, summary="Generate this week's brief (weekly job)")
def generate(db: DbSession, settings: AppSettings) -> BriefOut:
    brief = generate_brief(db, settings)
    if brief is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No price snapshots yet; run /admin/refresh first")
    return brief_out(brief, Language.EN)


@router.post("/briefs/broadcast", response_model=BroadcastOut, summary="SMS the latest brief to subscribed phones")
def broadcast(db: DbSession, gateway: Gateway) -> BroadcastOut:
    brief = latest_brief(db)
    if brief is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No weekly brief generated yet")
    users = list(db.scalars(select(User).where(User.brief_subscribed.is_(True), User.language.is_not(None))))
    sent = failed = 0
    for user in users:
        entry = deliver(db, gateway, user.phone, render_brief(brief, user.language))
        if entry.status == OutboxStatus.SENT:
            sent += 1
        else:
            failed += 1
    return BroadcastOut(recipients=len(users), sent=sent, failed=failed)


@router.get("/reports", response_model=list[ReportOut], summary="Field reports for review")
def get_reports(
    db: DbSession,
    status_filter: Annotated[ReportStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ReportOut]:
    return [report_out(r) for r in list_reports(db, status_filter, limit)]


@router.patch("/reports/{report_id}", response_model=ReportOut, summary="Accept or reject a field report")
def update_report(report_id: int, body: ReportStatusUpdate, db: DbSession) -> ReportOut:
    report = db.get(FieldReport, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    report.status = body.status
    db.commit()
    return report_out(report)
