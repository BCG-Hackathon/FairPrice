"""CSV ingestion: the contract with the data team (prices) and the model team (forecasts).

prices.csv     market_code,crop_code,observed_on,price,currency,unit_kg,source
forecasts.csv  market_code,crop_code,period_start,predicted_ugx_per_kg,lower,upper,model_version

Rows are upserted on their natural key, so re-uploading a file is safe.
"""

import csv
import io
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Crop, Market, PriceForecast, PriceObservation

MAX_REPORTED_ERRORS = 50
PRICE_COLUMNS = {"market_code", "crop_code", "observed_on", "price", "currency"}
FORECAST_COLUMNS = {"market_code", "crop_code", "period_start", "predicted_ugx_per_kg", "model_version"}


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    errors: list[str] = field(default_factory=list)

    def error(self, line: int, message: str) -> None:
        if len(self.errors) < MAX_REPORTED_ERRORS:
            self.errors.append(f"line {line}: {message}")


class _Lookups:
    def __init__(self, db: Session) -> None:
        self.markets = {m.code: m for m in db.scalars(select(Market))}
        self.crops = {c.code: c for c in db.scalars(select(Crop))}

    def resolve(self, row: dict[str, str]) -> tuple[Market, Crop]:
        market = self.markets.get(row["market_code"].strip().upper())
        crop = self.crops.get(row["crop_code"].strip().lower())
        if market is None:
            raise ValueError(f"unknown market_code {row['market_code']!r}")
        if crop is None:
            raise ValueError(f"unknown crop_code {row['crop_code']!r}")
        return market, crop


def to_ugx(price: float, currency: str, settings: Settings) -> float:
    currency = currency.upper()
    if currency == "UGX":
        return price
    if currency == "KES":
        return price * settings.kes_to_ugx
    raise ValueError(f"unsupported currency {currency!r}")


def import_prices_csv(db: Session, content: str, settings: Settings) -> ImportResult:
    lookups = _Lookups(db)

    def apply(row: dict[str, str], result: ImportResult) -> None:
        market, crop = lookups.resolve(row)
        observed_on = date.fromisoformat(row["observed_on"].strip())
        source_price = float(row["price"])
        unit_kg = float(row.get("unit_kg") or 1)
        if source_price <= 0 or unit_kg <= 0:
            raise ValueError("price and unit_kg must be positive")
        source = (row.get("source") or "import").strip().lower()[:32]
        price_ugx = to_ugx(source_price, row["currency"].strip(), settings) / unit_kg

        existing = db.scalar(
            select(PriceObservation).where(
                PriceObservation.market_id == market.id,
                PriceObservation.crop_id == crop.id,
                PriceObservation.observed_on == observed_on,
                PriceObservation.source == source,
            )
        )
        target = existing or PriceObservation(
            market_id=market.id, crop_id=crop.id, observed_on=observed_on, source=source
        )
        target.price_ugx_per_kg = round(price_ugx, 2)
        target.source_price = source_price
        target.source_currency = row["currency"].strip().upper()
        target.source_unit_kg = unit_kg
        if existing:
            result.updated += 1
        else:
            db.add(target)
            db.flush()  # duplicate keys later in the same file become updates
            result.created += 1

    return _run(db, content, PRICE_COLUMNS, apply)


def import_forecasts_csv(db: Session, content: str) -> ImportResult:
    lookups = _Lookups(db)

    def apply(row: dict[str, str], result: ImportResult) -> None:
        market, crop = lookups.resolve(row)
        period_start = date.fromisoformat(row["period_start"].strip())
        version = row["model_version"].strip()[:40]
        existing = db.scalar(
            select(PriceForecast).where(
                PriceForecast.market_id == market.id,
                PriceForecast.crop_id == crop.id,
                PriceForecast.period_start == period_start,
                PriceForecast.model_version == version,
            )
        )
        target = existing or PriceForecast(
            market_id=market.id, crop_id=crop.id, period_start=period_start, model_version=version
        )
        target.predicted_ugx_per_kg = float(row["predicted_ugx_per_kg"])
        target.lower_ugx_per_kg = float(row["lower"]) if row.get("lower") else None
        target.upper_ugx_per_kg = float(row["upper"]) if row.get("upper") else None
        if existing:
            result.updated += 1
        else:
            db.add(target)
            db.flush()  # duplicate keys later in the same file become updates
            result.created += 1

    return _run(db, content, FORECAST_COLUMNS, apply)


def _run(
    db: Session,
    content: str,
    required: set[str],
    apply: Callable[[dict[str, str], ImportResult], None],
) -> ImportResult:
    result = ImportResult()
    reader = csv.DictReader(io.StringIO(content.lstrip("﻿")))
    missing = required - set(reader.fieldnames or [])
    if missing:
        result.error(1, f"missing columns: {', '.join(sorted(missing))}")
        return result
    for line, row in enumerate(reader, start=2):
        try:
            apply(row, result)
        except (ValueError, KeyError) as exc:
            result.error(line, str(exc))
    db.commit()
    return result
