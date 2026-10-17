import hashlib
from collections import defaultdict
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import select

from app.deps import AppSettings, DbSession, Transport
from app.models import Category, Crop, Grade, Kiosk, Market, PriceForecast, PriceObservation
from app.schemas import (
    CompareOut,
    ForecastPoint,
    HistoryOut,
    HistoryPoint,
    MarketOptionOut,
    SnapshotItem,
    SnapshotOut,
)
from app.services import catalog, pricing
from app.services.offers import MarketOption, compare_markets
from app.services.snapshot import last_generated_at, list_snapshots
from app.services.grade_policy import grade_prices

router = APIRouter(prefix="/prices", tags=["prices"])


def require_crop(db: DbSession, code: str) -> Crop:
    crop = catalog.get_crop(db, code)
    if crop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown crop {code!r}")
    return crop


def require_market(db: DbSession, code: str) -> Market:
    market = catalog.get_market(db, code)
    if market is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown market {code!r}")
    return market


def require_kiosk(db: DbSession, code: str) -> Kiosk:
    kiosk = catalog.get_kiosk(db, code)
    if kiosk is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown kiosk {code!r}")
    return kiosk


def option_out(option: MarketOption, quantity_kg: float) -> MarketOptionOut:
    return MarketOptionOut(
        market_code=option.market.code,
        market_name=option.market.name,
        country=option.market.country,
        as_of=option.snapshot.as_of,
        market_price=option.market_price,
        change_pct=option.snapshot.change_pct,
        distance_km=option.distance_km,
        transport_ugx_per_kg=option.transport_ugx_per_kg,
        fair_farm_gate_price=option.fair_farm_gate_price,
        self_sell_net_per_kg=option.self_sell_net_per_kg,
        fair_farm_gate_total=round(option.fair_farm_gate_price * quantity_kg),
        self_sell_net_total=round(option.self_sell_net_per_kg * quantity_kg),
    )


@router.get(
    "/snapshot",
    response_model=SnapshotOut,
    summary="Current prices (ticker). Supports ETag / If-None-Match for low-bandwidth kiosks.",
)
def get_snapshot(
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    transport: Transport,
    market: str | None = None,
    category: Category | None = None,
    kiosk: Annotated[str | None, Query(description="Adds fair farm-gate prices for this village hub")] = None,
):
    generated_at = last_generated_at(db)
    etag = '"' + hashlib.sha256(f"{generated_at}|{market}|{category}|{kiosk}".encode()).hexdigest()[:16] + '"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})

    origin = require_kiosk(db, kiosk) if kiosk else None
    items = []
    for s in list_snapshots(db, market_code=market, category=category):
        item = SnapshotItem(
            market_code=s.market.code,
            market_name=s.market.name,
            country=s.market.country,
            crop_code=s.crop.code,
            crop_name=s.crop.name,
            category=s.crop.category,
            as_of=s.as_of,
            price_a=s.price_a,
            price_b=s.price_b,
            previous_price_a=s.previous_price_a,
            previous_as_of=s.previous_as_of,
            change_pct=s.change_pct,
            trend=pricing.trend_of(s.change_pct, settings.trend_flat_band_pct),
            forecast_next_a=s.forecast_next_a,
            forecast_source=s.forecast_source,
            data_source=s.data_source,
            b_sell_within_days=s.crop.b_sell_within_days,
        )
        if "wfp_snapshot" in s.data_source:
            item.price_c = grade_prices(s.price_b)["C"]
            item.pricing_notice = "Indicative A +4%, B base, C -5.5%; dated monthly source, not a current buyer offer."
        if origin is not None:
            cost = transport.estimate(origin, s.market).cost_ugx_per_kg
            margin = settings.fair_trader_margin
            item.transport_ugx_per_kg = cost
            item.fair_farm_gate_a = round(pricing.fair_farm_gate_price(s.price_a, cost, margin))
            item.fair_farm_gate_b = round(pricing.fair_farm_gate_price(s.price_b, cost, margin))
        items.append(item)

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "no-cache"  # cache, but revalidate with ETag
    return SnapshotOut(generated_at=generated_at, kiosk_code=kiosk.upper() if kiosk else None, items=items)


@router.get("/history", response_model=HistoryOut, summary="Weekly price series for graphs, plus forecasts")
def get_history(
    db: DbSession,
    crop: str,
    market: str,
    weeks: Annotated[int, Query(ge=1, le=104)] = 26,
) -> HistoryOut:
    crop_row = require_crop(db, crop)
    market_row = require_market(db, market)
    since = date.today() - timedelta(weeks=weeks)
    rows = db.scalars(
        select(PriceObservation)
        .where(
            PriceObservation.crop_id == crop_row.id,
            PriceObservation.market_id == market_row.id,
            PriceObservation.observed_on >= since,
        )
        .order_by(PriceObservation.observed_on)
    )
    by_date: dict[date, list[PriceObservation]] = defaultdict(list)
    for row in rows:
        by_date[row.observed_on].append(row)
    points = []
    for day, observations in sorted(by_date.items()):
        price_a = sum(o.price_ugx_per_kg for o in observations) / len(observations)
        points.append(
            HistoryPoint(
                date=day,
                price_a=round(price_a),
                price_b=round(price_a * crop_row.grade_b_factor),
                sources=sorted({o.source for o in observations}),
            )
        )

    last_day = points[-1].date if points else date.today()
    forecasts = db.scalars(
        select(PriceForecast)
        .where(
            PriceForecast.crop_id == crop_row.id,
            PriceForecast.market_id == market_row.id,
            PriceForecast.period_start > last_day,
        )
        .order_by(PriceForecast.period_start)
    )
    return HistoryOut(
        crop_code=crop_row.code,
        market_code=market_row.code,
        points=points,
        forecast=[
            ForecastPoint(
                period_start=f.period_start,
                predicted_a=f.predicted_ugx_per_kg,
                lower_a=f.lower_ugx_per_kg,
                upper_a=f.upper_ugx_per_kg,
                model_version=f.model_version,
            )
            for f in forecasts
        ],
    )


@router.get("/compare", response_model=CompareOut, summary="Markets ranked by fair farm-gate price after transport")
def compare(
    db: DbSession,
    settings: AppSettings,
    transport: Transport,
    crop: str,
    kiosk: str,
    grade: Grade = Grade.A,
    quantity_kg: Annotated[float, Query(gt=0)] = 100,
) -> CompareOut:
    crop_row = require_crop(db, crop)
    origin = require_kiosk(db, kiosk)
    options = compare_markets(db, crop_row, grade, origin, transport, settings)
    return CompareOut(
        crop_code=crop_row.code,
        grade=grade,
        kiosk_code=origin.code,
        quantity_kg=quantity_kg,
        trader_margin=settings.fair_trader_margin,
        options=[option_out(o, quantity_kg) for o in options],
    )
