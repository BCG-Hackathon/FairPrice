from fastapi import APIRouter
from sqlalchemy import func, select

from app.deps import AppSettings, DbSession
from app.models import Crop, FieldReport, Market, MarketBrief, PriceObservation, ReportStatus
from app.schemas import SourceFreshness, StatusOut
from app.services.snapshot import last_generated_at

router = APIRouter(tags=["status"])


@router.get("/status", response_model=StatusOut, summary="Data freshness and system status")
def get_status(db: DbSession, settings: AppSettings) -> StatusOut:
    sources = db.execute(
        select(
            PriceObservation.source,
            func.count(PriceObservation.id),
            func.max(PriceObservation.observed_on),
        ).group_by(PriceObservation.source)
    ).all()
    report_counts = dict(
        db.execute(select(FieldReport.status, func.count(FieldReport.id)).group_by(FieldReport.status)).all()
    )
    return StatusOut(
        environment=settings.environment,
        snapshot_generated_at=last_generated_at(db),
        latest_brief_at=db.scalar(select(func.max(MarketBrief.generated_at))),
        sources=[SourceFreshness(source=s, observations=n, latest_observed_on=d) for s, n, d in sources],
        markets=db.scalar(select(func.count(Market.id))) or 0,
        crops=db.scalar(select(func.count(Crop.id))) or 0,
        reports_pending=report_counts.get(ReportStatus.PENDING, 0),
        reports_flagged=report_counts.get(ReportStatus.FLAGGED, 0),
    )
