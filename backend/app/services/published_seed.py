"""Load reviewed ML snapshot records into the teammate backend's SQLAlchemy database.

Never manufacture prices for today. Synthetic seed code is only used in explicit demo mode.
"""
import re
from datetime import date
from sqlalchemy import delete, select
from app.models import Category, Crop, Market, PriceObservation, PriceForecast, PublishedPrice
from app.services.published import CROP_META, load_snapshot
from app.services.snapshot import refresh_snapshots


def market_code(name):
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")[:32]


def seed_published(db, settings):
    if db.scalar(select(PriceObservation.id).where(PriceObservation.source == "seed").limit(1)):
        raise ValueError("Published mode requires a separate database without synthetic seed observations.")
    snapshot = load_snapshot()
    # Keep full provenance in the new public-record table; source branches remain intact.
    chosen = {}
    for r in snapshot["rows"]:
        key = (r["crop"], r["market"])
        rank = (r["last_month"], r["observed_price_type"] == "Wholesale")
        old = chosen.get(key)
        if old is None or rank > (old["last_month"], old["observed_price_type"] == "Wholesale"):
            chosen[key] = r
    db.execute(delete(PublishedPrice))
    for index, (crop, meta) in enumerate(CROP_META.items()):
        if db.scalar(select(Crop).where(Crop.code == crop)) is None:
            db.add(Crop(code=crop, name=meta[0], category=Category.VEGETABLES_GRAINS,
                        grade_b_factor=1/1.04, b_sell_within_days=0, sort_order=index))
    db.flush()
    crops = {c.code: c for c in db.scalars(select(Crop))}
    for r in chosen.values():
        code = market_code(r["market"])
        market = db.scalar(select(Market).where(Market.code == code))
        if market is None:
            market = Market(code=code, name=r["market"], country="UG", region=r["sub_region"],
                            latitude=r["latitude"], longitude=r["longitude"], currency="UGX",
                            sort_order=0 if r["core_area"] else 1)
            db.add(market)
            db.flush()
        crop = crops[r["crop"]]
        db.add(PublishedPrice(crop=r["crop"], market=r["market"], payload={
            **r, "snapshot_generated_at": snapshot["generated_at"], "snapshot_data_end": snapshot["data_end"]}))
        day = date.fromisoformat(r["last_month"] + "-01")
        existing = db.scalar(select(PriceObservation).where(
            PriceObservation.crop_id == crop.id, PriceObservation.market_id == market.id,
            PriceObservation.observed_on == day, PriceObservation.source == "wfp_snapshot"))
        if existing is None:
            db.add(PriceObservation(crop_id=crop.id, market_id=market.id, observed_on=day,
                                   price_ugx_per_kg=r["market_price"], source="wfp_snapshot",
                                   source_price=r["observed_price"], source_currency="UGX", source_unit_kg=1))
        else:
            existing.price_ugx_per_kg = r["market_price"]
            existing.source_price = r["observed_price"]
        forecast_day = date.fromisoformat(r["forecast_month"] + "-01")
        fc = db.scalar(select(PriceForecast).where(PriceForecast.crop_id == crop.id,
            PriceForecast.market_id == market.id, PriceForecast.period_start == forecast_day,
            PriceForecast.model_version == "team-2026-10-16"))
        if fc is None:
            db.add(PriceForecast(crop_id=crop.id, market_id=market.id, period_start=forecast_day,
                                predicted_ugx_per_kg=r["market_price_forecast"] * 1.04,
                                model_version="team-2026-10-16"))
        else:
            fc.predicted_ugx_per_kg = r["market_price_forecast"] * 1.04
    db.commit()
    refresh_snapshots(db, settings)
