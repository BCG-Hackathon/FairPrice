"""Field price reports from group leaders (SMS) and kiosk tablets (offline batch sync).

Status rules:
  * unregistered numbers (role=farmer)            -> pending (needs review)
  * trusted reporters / kiosks, within threshold  -> accepted (feeds next refresh)
  * more than `report_outlier_threshold` off      -> flagged (needs review)
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Channel, Crop, FieldReport, Grade, Market, ReportStatus, User, UserRole, utcnow
from app.services.snapshot import get_snapshot


@dataclass(frozen=True)
class ReportInput:
    reporter_phone: str
    channel: Channel
    crop: Crop
    market: Market
    grade: Grade
    price_ugx_per_kg: float
    reported_at: datetime | None = None
    client_ref: str | None = None
    note: str | None = None


def submit_report(db: Session, data: ReportInput, settings: Settings) -> tuple[FieldReport, bool]:
    """Store a report. Returns (report, created); re-sending the same client_ref is a no-op."""
    client_ref = data.client_ref or uuid.uuid4().hex
    existing = db.scalar(select(FieldReport).where(FieldReport.client_ref == client_ref))
    if existing:
        return existing, False

    deviation = _deviation(db, data)
    report = FieldReport(
        client_ref=client_ref,
        reporter_phone=data.reporter_phone,
        channel=data.channel,
        market_id=data.market.id,
        crop_id=data.crop.id,
        grade=data.grade,
        price_ugx_per_kg=data.price_ugx_per_kg,
        reported_at=data.reported_at or utcnow(),
        status=_status(db, data, deviation, settings),
        deviation_pct=round(deviation * 100, 1) if deviation is not None else None,
        note=data.note,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report, True


def _deviation(db: Session, data: ReportInput) -> float | None:
    snapshot = get_snapshot(db, data.market.id, data.crop.id)
    if snapshot is None:
        return None
    reference = snapshot.price_a if data.grade == Grade.A else snapshot.price_b
    return (data.price_ugx_per_kg - reference) / reference if reference else None


def _status(db: Session, data: ReportInput, deviation: float | None, settings: Settings) -> ReportStatus:
    if deviation is not None and abs(deviation) > settings.report_outlier_threshold:
        return ReportStatus.FLAGGED
    if data.channel in (Channel.KIOSK, Channel.ADMIN):
        return ReportStatus.ACCEPTED
    user = db.get(User, data.reporter_phone)
    if user and user.role in (UserRole.REPORTER, UserRole.KIOSK):
        return ReportStatus.ACCEPTED
    return ReportStatus.PENDING


def list_reports(db: Session, status: ReportStatus | None = None, limit: int = 100) -> list[FieldReport]:
    stmt = select(FieldReport).order_by(FieldReport.received_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(FieldReport.status == status)
    return list(db.scalars(stmt).unique())
