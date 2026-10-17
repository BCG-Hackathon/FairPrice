"""ORM models.

Kept Azure SQL compatible: every string has a length (no VARCHAR(max) in indexes),
human-readable text uses Unicode (NVARCHAR), enums are stored as plain strings,
unique columns are never NULL, and all timestamps are naive UTC.
"""

from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Unicode,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    """Naive UTC timestamp (SQLite drops tz info; we normalise everywhere)."""
    return datetime.now(UTC).replace(tzinfo=None)


def _enum(cls: type[StrEnum]) -> SAEnum:
    return SAEnum(
        cls,
        native_enum=False,
        length=24,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


class Category(StrEnum):
    FRUITS = "fruits"
    VEGETABLES_GRAINS = "vegetables_grains"
    CASH_CROPS = "cash_crops"


class Grade(StrEnum):
    A = "A"  # standard / export: firm, unblemished, travels well
    B = "B"  # ripe / blemished / mixed: sell within days


class Language(StrEnum):
    EN = "en"
    SW = "sw"
    ACH = "ach"


class UserRole(StrEnum):
    FARMER = "farmer"
    REPORTER = "reporter"  # trusted group leader
    KIOSK = "kiosk"  # kiosk attendant device / number


class ReportStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    FLAGGED = "flagged"
    REJECTED = "rejected"


class Channel(StrEnum):
    SMS = "sms"
    USSD = "ussd"
    KIOSK = "kiosk"
    ADMIN = "admin"


class OutboxStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(Unicode(80))
    country: Mapped[str] = mapped_column(String(2))  # ISO: UG, KE
    region: Mapped[str] = mapped_column(Unicode(80))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Kiosk(Base):
    """A village hub with a solar tablet. Used as the farmer's origin for transport costs."""

    __tablename__ = "kiosks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(Unicode(80))
    district: Mapped[str] = mapped_column(Unicode(80))
    country: Mapped[str] = mapped_column(String(2), default="UG")
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)


class Crop(Base):
    __tablename__ = "crops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(Unicode(80))  # English display name
    category: Mapped[Category] = mapped_column(_enum(Category))
    grade_b_factor: Mapped[float] = mapped_column(Float)  # B price = A price x factor
    b_sell_within_days: Mapped[int] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class PriceObservation(Base):
    """An observed Category A market price, normalised to UGX per kg."""

    __tablename__ = "price_observations"
    __table_args__ = (
        UniqueConstraint("market_id", "crop_id", "observed_on", "source", name="uq_obs"),
        Index("ix_obs_lookup", "crop_id", "market_id", "observed_on"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"))
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"))
    observed_on: Mapped[date] = mapped_column(Date)
    price_ugx_per_kg: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32))  # seed | wfp | kamis | ucda | field | ...
    source_price: Mapped[float] = mapped_column(Float)
    source_currency: Mapped[str] = mapped_column(String(3))
    source_unit_kg: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PriceForecast(Base):
    """Forecasts written by the model team (via CSV import)."""

    __tablename__ = "price_forecasts"
    __table_args__ = (
        UniqueConstraint("market_id", "crop_id", "period_start", "model_version", name="uq_fc"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"))
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"))
    period_start: Mapped[date] = mapped_column(Date)
    predicted_ugx_per_kg: Mapped[float] = mapped_column(Float)
    lower_ugx_per_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper_ugx_per_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PriceSnapshot(Base):
    """Precomputed current price per market x crop. This is what channels serve."""

    __tablename__ = "price_snapshots"
    __table_args__ = (UniqueConstraint("market_id", "crop_id", name="uq_snapshot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"))
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"))
    as_of: Mapped[date] = mapped_column(Date)
    price_a: Mapped[float] = mapped_column(Float)
    price_b: Mapped[float] = mapped_column(Float)
    previous_price_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    previous_as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    forecast_next_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    forecast_source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    data_source: Mapped[str] = mapped_column(String(64))
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    market: Mapped[Market] = relationship(lazy="joined")
    crop: Mapped[Crop] = relationship(lazy="joined")


class User(Base):
    """A phone number that has used SMS/USSD. Language is chosen once and remembered."""

    __tablename__ = "users"

    phone: Mapped[str] = mapped_column(String(20), primary_key=True)
    language: Mapped[Language | None] = mapped_column(_enum(Language), nullable=True)
    role: Mapped[UserRole] = mapped_column(_enum(UserRole), default=UserRole.FARMER)
    home_kiosk_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    brief_subscribed: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_menu_path: Mapped[str] = mapped_column(String(100), default="")  # SMS menu state
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class UssdSession(Base):
    """Remembers the language a USSD session started with, so menu step indices stay stable."""

    __tablename__ = "ussd_sessions"

    session_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    phone: Mapped[str] = mapped_column(String(20))
    language_at_start: Mapped[Language | None] = mapped_column(_enum(Language), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class FieldReport(Base):
    """A price seen in the field, reported by SMS (group leaders) or the kiosk tablet."""

    __tablename__ = "field_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_ref: Mapped[str] = mapped_column(String(64), unique=True)  # idempotency key
    reporter_phone: Mapped[str] = mapped_column(String(20))
    channel: Mapped[Channel] = mapped_column(_enum(Channel))
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"))
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"))
    grade: Mapped[Grade] = mapped_column(_enum(Grade))
    price_ugx_per_kg: Mapped[float] = mapped_column(Float)
    reported_at: Mapped[datetime] = mapped_column(DateTime)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status: Mapped[ReportStatus] = mapped_column(_enum(ReportStatus))
    deviation_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(Unicode(200), nullable=True)

    market: Mapped[Market] = relationship(lazy="joined")
    crop: Mapped[Crop] = relationship(lazy="joined")


class MarketBrief(Base):
    """Weekly brief stored as structured movers; rendered per language at read time."""

    __tablename__ = "market_briefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_end: Mapped[date] = mapped_column(Date)
    items: Mapped[list] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SmsOutbox(Base):
    """Every outbound SMS. Powers the phone simulator and gives an audit trail."""

    __tablename__ = "sms_outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    to_phone: Mapped[str] = mapped_column(String(20), index=True)
    message: Mapped[str] = mapped_column(Unicode(640))
    status: Mapped[OutboxStatus] = mapped_column(_enum(OutboxStatus))
    provider: Mapped[str] = mapped_column(String(32))
    provider_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
