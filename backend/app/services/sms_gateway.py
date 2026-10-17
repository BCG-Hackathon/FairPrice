"""Outbound SMS. Every message is written to the outbox (audit + phone simulator).

`OutboxGateway` only records messages (local dev, demo simulator). An Africa's
Talking gateway can implement the same `SmsGateway` protocol later.
"""

import logging
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OutboxStatus, SmsOutbox

logger = logging.getLogger(__name__)


class SmsGateway(Protocol):
    name: str

    def send(self, to_phone: str, message: str) -> str | None:
        """Send and return the provider's message id. Raise on failure."""
        ...


class OutboxGateway:
    name = "outbox"

    def send(self, to_phone: str, message: str) -> str | None:
        logger.info("SMS to %s: %s", to_phone, message.replace("\n", " | "))
        return None


def deliver(db: Session, gateway: SmsGateway, to_phone: str, message: str) -> SmsOutbox:
    entry = SmsOutbox(to_phone=to_phone, message=message, provider=gateway.name, status=OutboxStatus.QUEUED)
    try:
        entry.provider_ref = gateway.send(to_phone, message)
        entry.status = OutboxStatus.SENT
    except Exception:
        logger.exception("SMS delivery to %s failed", to_phone)
        entry.status = OutboxStatus.FAILED
    db.add(entry)
    db.commit()
    return entry


def outbox_for(db: Session, phone: str, limit: int = 20) -> list[SmsOutbox]:
    stmt = (
        select(SmsOutbox)
        .where(SmsOutbox.to_phone == phone)
        .order_by(SmsOutbox.created_at.desc(), SmsOutbox.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))
