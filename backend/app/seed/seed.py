"""Seed reference data and a realistic, clearly labelled demo price history.

Demo prices use source="seed" so they are never confused with real data, and are
regenerated relative to today so "last updated" stays current. The data team
replaces them by importing WFP/KAMIS/UCDA prices via /admin/prices/import.

Run manually:  python -m app.seed.seed
"""

import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Category, Crop, Kiosk, Market, PriceObservation, User, UserRole

DATA_DIR = Path(__file__).parent / "data"
SEED_SOURCE = "seed"
SEED_WEEKS = 26
RANDOM_SEED = 42
SEASONAL_AMPLITUDE = 0.12

# Town-hub premium vs Gulu. Kenya hubs pay more for export-quality produce (the "abroad" price).
MARKET_PREMIUM: dict[str, float] = {
    "GULU": 1.00,
    "LIRA": 1.06,
    "KITGUM": 0.95,
    "KAMPALA": 1.30,
    "KISUMU": 1.45,
    "NAIROBI": 1.70,
}
EXPORT_CROPS = {"avocado", "coffee"}
EXPORT_BONUS_KE = 0.15

DEMO_REPORTER_PHONE = "+256700000001"  # trusted group leader for the demo


def _load(name: str) -> list[dict]:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def seed_reference_data(db: Session) -> bool:
    """Insert markets, kiosks and crops if the DB is empty. Returns True if it seeded."""
    if db.scalar(select(Market.id).limit(1)) is not None:
        return False
    db.add_all(Market(**m) for m in _load("markets.json"))
    db.add_all(Kiosk(**k) for k in _load("kiosks.json"))
    for c in _load("crops.json"):
        db.add(
            Crop(
                code=c["code"],
                name=c["name"],
                category=Category(c["category"]),
                grade_b_factor=c["grade_b_factor"],
                b_sell_within_days=c["b_sell_within_days"],
                sort_order=c["sort_order"],
            )
        )
    db.add(User(phone=DEMO_REPORTER_PHONE, role=UserRole.REPORTER))
    db.commit()
    return True


def seed_demo_prices(db: Session, settings: Settings, today: date | None = None) -> int:
    """Generate weekly demo observations for the last SEED_WEEKS weeks (only if none exist)."""
    if db.scalar(select(PriceObservation.id).limit(1)) is not None:
        return 0
    rng = random.Random(RANDOM_SEED)
    today = today or date.today()
    last_monday = today - timedelta(days=today.weekday())
    weeks = [last_monday - timedelta(weeks=w) for w in reversed(range(SEED_WEEKS))]
    crop_params = {c["code"]: c for c in _load("crops.json")}
    markets = list(db.scalars(select(Market)))
    crops = list(db.scalars(select(Crop)))

    count = 0
    for crop in crops:
        params = crop_params[crop.code]
        # One supply/demand trend per crop shared by all markets, plus a small local wobble.
        crop_walk = _bounded_walk(rng, len(weeks), step=0.025, bound=0.12)
        for market in markets:
            premium = MARKET_PREMIUM.get(market.code, 1.0)
            if market.country == "KE" and crop.code in EXPORT_CROPS:
                premium += EXPORT_BONUS_KE
            local_walk = _bounded_walk(rng, len(weeks), step=0.01, bound=0.04)
            for week, shared, local in zip(weeks, crop_walk, local_walk, strict=True):
                day = week.timetuple().tm_yday
                seasonal = SEASONAL_AMPLITUDE * math.cos(2 * math.pi * (day - params["season_peak_day"]) / 365)
                price_ugx = params["base_ugx_per_kg"] * premium * (1 + seasonal + shared + local)
                source_price = price_ugx / settings.kes_to_ugx if market.currency == "KES" else price_ugx
                db.add(
                    PriceObservation(
                        market_id=market.id,
                        crop_id=crop.id,
                        observed_on=week,
                        price_ugx_per_kg=round(price_ugx, 2),
                        source=SEED_SOURCE,
                        source_price=round(source_price, 2),
                        source_currency=market.currency,
                        source_unit_kg=1.0,
                    )
                )
                count += 1
    db.commit()
    return count


def _bounded_walk(rng: random.Random, n: int, step: float, bound: float) -> list[float]:
    value, values = 0.0, []
    for _ in range(n):
        value = max(-bound, min(bound, value + rng.gauss(0, step)))
        values.append(value)
    return values


def run(db: Session, settings: Settings) -> None:
    from app.services.briefs import generate_brief
    from app.services.snapshot import refresh_snapshots

    seed_reference_data(db)
    if seed_demo_prices(db, settings):
        refresh_snapshots(db, settings)
        generate_brief(db, settings)


if __name__ == "__main__":
    from app.db import Base, build_engine, build_session_factory

    settings = get_settings()
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)
    with build_session_factory(engine)() as session:
        run(session, settings)
    print("Seed complete.")
