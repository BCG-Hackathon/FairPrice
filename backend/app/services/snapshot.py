"""Builds the price snapshot that every channel serves.

For each market x crop:
  * current Category A price = latest observed price (mean across sources on that date),
    overridden by the median of accepted field reports if they are newer;
  * previous price = latest observation at least a week older (for "% vs last week");
  * forecast = the model team's next-period forecast, else a naive 4-week trend.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import mean, median

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (
    Category,
    Crop,
    FieldReport,
    Grade,
    Market,
    PriceForecast,
    PriceObservation,
    PriceSnapshot,
    ReportStatus,
    utcnow,
)
from app.services.pricing import change_pct
from app.services.grade_policy import grade_prices

PREVIOUS_MIN_GAP_DAYS = 6  # "last week" = an observation at least ~a week older
NAIVE_TREND_POINTS = 4


@dataclass(frozen=True)
class RefreshResult:
    snapshots: int
    generated_at: datetime


def refresh_snapshots(db: Session, settings: Settings) -> RefreshResult:
    generated_at = utcnow()
    crops = {c.id: c for c in db.scalars(select(Crop))}

    series: dict[tuple[int, int], dict[date, list[tuple[float, str]]]] = defaultdict(lambda: defaultdict(list))
    for obs in db.scalars(select(PriceObservation)):
        series[(obs.market_id, obs.crop_id)][obs.observed_on].append((obs.price_ugx_per_kg, obs.source))

    window_start = generated_at - timedelta(days=settings.field_report_window_days)
    field: dict[tuple[int, int], list[FieldReport]] = defaultdict(list)
    for report in db.scalars(
        select(FieldReport).where(
            FieldReport.status == ReportStatus.ACCEPTED, FieldReport.reported_at >= window_start
        )
    ):
        field[(report.market_id, report.crop_id)].append(report)

    db.execute(delete(PriceSnapshot))
    count = 0
    for key, by_date in series.items():
        market_id, crop_id = key
        crop = crops[crop_id]
        dates = sorted(by_date)
        points = [(d, mean(p for p, _ in by_date[d])) for d in dates]
        as_of, price_a = points[-1]
        sources = sorted({s for _, s in by_date[as_of]})

        reports = [r for r in field.get(key, []) if r.reported_at.date() > as_of]
        if reports:
            price_a = median(_as_grade_a(r, crop) for r in reports)
            as_of = max(r.reported_at.date() for r in reports)
            sources.append("field")

        previous = next(
            ((d, p) for d, p in reversed(points) if d <= as_of - timedelta(days=PREVIOUS_MIN_GAP_DAYS)),
            None,
        )
        forecast, forecast_source = _forecast(db, market_id, crop_id, as_of, points)
        # WFP values are ungraded base estimates, never observed A-grade offers.
        adjusted = grade_prices(price_a) if "wfp_snapshot" in sources else None

        db.add(
            PriceSnapshot(
                market_id=market_id,
                crop_id=crop_id,
                as_of=as_of,
                price_a=adjusted["A"] if adjusted else round(price_a),
                price_b=adjusted["B"] if adjusted else round(price_a * crop.grade_b_factor),
                previous_price_a=round(previous[1]) if previous else None,
                previous_as_of=previous[0] if previous else None,
                change_pct=change_pct(price_a, previous[1]) if previous else None,
                forecast_next_a=round(forecast) if forecast is not None else None,
                forecast_source=forecast_source,
                data_source="+".join(sources),
                generated_at=generated_at,
            )
        )
        count += 1
    db.commit()
    return RefreshResult(snapshots=count, generated_at=generated_at)


def _as_grade_a(report: FieldReport, crop: Crop) -> float:
    if report.grade == Grade.B and crop.grade_b_factor > 0:
        return report.price_ugx_per_kg / crop.grade_b_factor
    return report.price_ugx_per_kg


def _forecast(
    db: Session, market_id: int, crop_id: int, as_of: date, points: list[tuple[date, float]]
) -> tuple[float | None, str | None]:
    model = db.scalar(
        select(PriceForecast)
        .where(
            PriceForecast.market_id == market_id,
            PriceForecast.crop_id == crop_id,
            PriceForecast.period_start > as_of,
        )
        .order_by(PriceForecast.period_start, PriceForecast.created_at.desc())
        .limit(1)
    )
    if model:
        return model.predicted_ugx_per_kg, f"model:{model.model_version}"
    recent = [p for _, p in points[-(NAIVE_TREND_POINTS + 1):]]
    if len(recent) < 2:
        return None, None
    weekly_delta = (recent[-1] - recent[0]) / (len(recent) - 1)
    return max(0.0, recent[-1] + weekly_delta), "naive_trend"


def list_snapshots(
    db: Session, market_code: str | None = None, category: Category | None = None
) -> list[PriceSnapshot]:
    stmt = (
        select(PriceSnapshot)
        .join(PriceSnapshot.market)
        .join(PriceSnapshot.crop)
        .order_by(Market.sort_order, Crop.sort_order)
    )
    if market_code:
        stmt = stmt.where(Market.code == market_code.upper())
    if category:
        stmt = stmt.where(Crop.category == category)
    return list(db.scalars(stmt).unique())


def get_snapshot(db: Session, market_id: int, crop_id: int) -> PriceSnapshot | None:
    return db.scalar(
        select(PriceSnapshot).where(PriceSnapshot.market_id == market_id, PriceSnapshot.crop_id == crop_id)
    )


def last_generated_at(db: Session) -> datetime | None:
    return db.scalar(select(func.max(PriceSnapshot.generated_at)))
