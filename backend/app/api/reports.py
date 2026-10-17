from datetime import UTC, datetime

from fastapi import APIRouter

from app.deps import AppSettings, DbSession
from app.models import Channel
from app.schemas import ReportBatchIn, ReportBatchOut, ReportResult
from app.services import catalog
from app.services.reports import ReportInput, submit_report

router = APIRouter(prefix="/reports", tags=["field reports"])


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


@router.post(
    "",
    response_model=ReportBatchOut,
    summary="Submit field price reports from a kiosk tablet (batch, idempotent by client_ref)",
)
def submit_reports(body: ReportBatchIn, db: DbSession, settings: AppSettings) -> ReportBatchOut:
    """Tablets queue reports while offline and send them in one batch when signal returns.
    Re-sending a report with the same `client_ref` returns the stored result instead of duplicating it."""
    results = []
    for item in body.reports:
        crop = catalog.get_crop(db, item.crop_code)
        market = catalog.get_market(db, item.market_code)
        if crop is None or market is None:
            missing = "crop_code" if crop is None else "market_code"
            results.append(ReportResult(client_ref=item.client_ref, created=False, status=None, error=f"unknown {missing}"))
            continue
        report, created = submit_report(
            db,
            ReportInput(
                reporter_phone=item.reporter_phone,
                channel=Channel.KIOSK,
                crop=crop,
                market=market,
                grade=item.grade,
                price_ugx_per_kg=item.price_ugx_per_kg,
                reported_at=_naive_utc(item.reported_at),
                client_ref=item.client_ref,
                note=item.note,
            ),
            settings,
        )
        results.append(
            ReportResult(
                client_ref=report.client_ref,
                created=created,
                status=report.status,
                deviation_pct=report.deviation_pct,
            )
        )
    return ReportBatchOut(results=results)
