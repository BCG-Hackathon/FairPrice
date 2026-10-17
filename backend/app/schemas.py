"""Pydantic request/response models (the API contract the frontend builds against)."""

from datetime import UTC, date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from app.models import Category, Grade, Language, OutboxStatus, ReportStatus
from app.services.pricing import Trend, Verdict


def _as_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


# DB timestamps are naive UTC; always expose them with an explicit 'Z'.
UtcDateTime = Annotated[datetime, PlainSerializer(_as_utc_iso, return_type=str)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Catalog ----------

class CropOut(ORMModel):
    code: str
    name: str
    category: Category
    grade_b_factor: float
    b_sell_within_days: int


class MarketOut(ORMModel):
    code: str
    name: str
    country: str
    region: str
    latitude: float
    longitude: float
    currency: str


class KioskOut(ORMModel):
    code: str
    name: str
    district: str
    country: str
    latitude: float
    longitude: float


class GradeStandard(BaseModel):
    title: str
    points: list[str]
    image: str


class GradeStandardsOut(BaseModel):
    crop_code: str
    A: GradeStandard
    B: GradeStandard


# ---------- Prices ----------

class SnapshotItem(BaseModel):
    market_code: str
    market_name: str
    country: str
    crop_code: str
    crop_name: str
    category: Category
    as_of: date
    price_a: float
    price_b: float
    price_c: float | None = None
    pricing_notice: str | None = None
    previous_price_a: float | None
    previous_as_of: date | None
    change_pct: float | None
    trend: Trend
    forecast_next_a: float | None
    forecast_source: str | None
    data_source: str
    b_sell_within_days: int
    # Only when a kiosk is given: what a fair buyer should pay at that village.
    transport_ugx_per_kg: float | None = None
    fair_farm_gate_a: float | None = None
    fair_farm_gate_b: float | None = None


class SnapshotOut(BaseModel):
    generated_at: UtcDateTime | None
    currency: str = "UGX"
    unit: str = "kg"
    kiosk_code: str | None = None
    items: list[SnapshotItem]


class HistoryPoint(BaseModel):
    date: date
    price_a: float
    price_b: float
    sources: list[str]


class ForecastPoint(BaseModel):
    period_start: date
    predicted_a: float
    lower_a: float | None
    upper_a: float | None
    model_version: str


class HistoryOut(BaseModel):
    crop_code: str
    market_code: str
    currency: str = "UGX"
    unit: str = "kg"
    points: list[HistoryPoint]
    forecast: list[ForecastPoint]


class MarketOptionOut(BaseModel):
    market_code: str
    market_name: str
    country: str
    as_of: date
    market_price: float
    change_pct: float | None
    distance_km: float
    transport_ugx_per_kg: float
    fair_farm_gate_price: float
    self_sell_net_per_kg: float
    fair_farm_gate_total: float
    self_sell_net_total: float


class CompareOut(BaseModel):
    crop_code: str
    grade: Grade
    kiosk_code: str
    quantity_kg: float
    trader_margin: float
    options: list[MarketOptionOut]


# ---------- Offer check ----------

class OfferCheckIn(BaseModel):
    crop_code: str
    grade: Grade = Grade.A
    offer_ugx_per_kg: float = Field(gt=0)
    quantity_kg: float = Field(default=100, gt=0)
    kiosk_code: str
    market_code: str | None = Field(default=None, description="Reference market; best market if omitted")
    language: Language = Language.EN


class OfferCheckOut(BaseModel):
    verdict: Verdict
    offer_ugx_per_kg: float
    fair_price_ugx_per_kg: float
    pct_of_fair: float
    gap_per_kg: float
    total_loss_ugx: float
    quantity_kg: float
    reference: MarketOptionOut
    best: MarketOptionOut
    message: str


# ---------- Field reports ----------

class ReportIn(BaseModel):
    client_ref: str | None = Field(default=None, max_length=64, description="Idempotency key from the device")
    reporter_phone: str = Field(max_length=20)
    crop_code: str
    market_code: str
    grade: Grade
    price_ugx_per_kg: float = Field(gt=0)
    reported_at: datetime | None = None
    note: str | None = Field(default=None, max_length=200)


class ReportBatchIn(BaseModel):
    reports: list[ReportIn] = Field(min_length=1, max_length=200)


class ReportResult(BaseModel):
    client_ref: str | None
    created: bool
    status: ReportStatus | None
    deviation_pct: float | None = None
    error: str | None = None


class ReportBatchOut(BaseModel):
    results: list[ReportResult]


class ReportOut(BaseModel):
    id: int
    client_ref: str
    reporter_phone: str
    channel: str
    crop_code: str
    market_code: str
    grade: Grade
    price_ugx_per_kg: float
    reported_at: UtcDateTime
    received_at: UtcDateTime
    status: ReportStatus
    deviation_pct: float | None
    note: str | None


class ReportStatusUpdate(BaseModel):
    status: ReportStatus


# ---------- Briefs ----------

class BriefItem(BaseModel):
    crop_code: str
    market_code: str
    market_name: str
    price_a: float
    change_pct: float
    direction: str


class BriefOut(BaseModel):
    generated_at: UtcDateTime
    period_end: date
    language: Language
    items: list[BriefItem]
    text: str


class BroadcastOut(BaseModel):
    recipients: int
    sent: int
    failed: int


# ---------- Channels ----------

class SmsReply(BaseModel):
    reply: str
    outbox_id: int


class OutboxItem(ORMModel):
    id: int
    to_phone: str
    message: str
    status: OutboxStatus
    provider: str
    created_at: UtcDateTime


# ---------- Admin / status ----------

class RefreshOut(BaseModel):
    snapshots: int
    generated_at: UtcDateTime


class ImportOut(BaseModel):
    created: int
    updated: int
    errors: list[str]


class SourceFreshness(BaseModel):
    source: str
    observations: int
    latest_observed_on: date | None


class StatusOut(BaseModel):
    environment: str
    snapshot_generated_at: UtcDateTime | None
    latest_brief_at: UtcDateTime | None
    sources: list[SourceFreshness]
    markets: int
    crops: int
    reports_pending: int
    reports_flagged: int
