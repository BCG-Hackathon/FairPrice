"""SMS price updates: one endpoint for farmers, one for buyers/suppliers.

Both are kiosk-staff actions (they can message many people), default to a dry run that
returns the exact text, and log every real send in sms_outbox.
"""

import re
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.api.buyers import secure_admin
from app.deps import AppSettings, DbSession
from app.models import BuyerListing, OutboxStatus, SmsContact, SmsOutbox, utcnow
from app.services import bulksms
from app.services.sms_updates import buyer_update, farmer_update

router = APIRouter(prefix="/api/sms", tags=["sms updates"])

E164 = r"^\+[1-9][0-9]{7,14}$"


class FarmerUpdateIn(BaseModel):
    phones: list[Annotated[str, Field(pattern=E164)]] = Field(default=[], max_length=100)
    group: str | None = Field(default=None, max_length=100, description="BulkSMS phonebook group name")
    categories: list[Literal["vegetables", "fruits", "grains"]] = ["vegetables", "fruits", "grains"]
    language: Literal["en", "sw"] = "en"
    dry_run: bool = Field(default=True, description="Preview only. Set false to send.")
    consent_confirmed: bool = Field(default=False, description="Recipients agreed to receive FairPrice SMS")

    @model_validator(mode="after")
    def _recipients(self) -> "FarmerUpdateIn":
        if not self.phones and not self.group:
            raise ValueError("Give phones or a BulkSMS group")
        return self


class BuyerUpdateIn(BaseModel):
    crop: str | None = Field(default=None, description="Only buyers of this crop (default: all)")
    language: Literal["en", "sw"] = "en"
    dry_run: bool = Field(default=True, description="Preview only. Set false to send.")


def _deliver(db, settings, text: str, to: str | None = None, group: str | None = None) -> list[dict]:
    """Send one SMS (to a number or a group) and log each recipient; failures are reported, not raised."""
    allowed = bulksms.allowed_recipients(settings)
    if allowed and (group or to not in allowed):
        return [{"to": to or f"group:{group}", "status": "skipped",
                 "error": "Not on the test allowlist (COMMS_ALLOWED_RECIPIENTS)"}]
    try:
        sent = bulksms.send(settings, text, to=to, group=group)
    except bulksms.SmsError as exc:
        db.add(SmsOutbox(to_phone=(to or "group")[:20], message=text, status=OutboxStatus.FAILED, provider="bulksms"))
        db.commit()
        return [{"to": to or f"group:{group}", "status": "failed", "error": str(exc)}]
    for s in sent:
        db.add(SmsOutbox(
            to_phone=s.to[:20] or "unknown", message=text, provider="bulksms", provider_ref=s.message_id,
            status=OutboxStatus.FAILED if s.status == "FAILED" else OutboxStatus.SENT,
        ))
    db.commit()
    return [{"to": s.to, "status": "sent" if s.status != "FAILED" else "failed", "message_id": s.message_id} for s in sent]


def _mode(settings, dry_run: bool) -> str:
    if dry_run:
        return "dry_run"
    if not bulksms.configured(settings):
        raise HTTPException(409, "BulkSMS is not configured (BULKSMS_TOKEN_ID / BULKSMS_TOKEN_SECRET)")
    return "send"


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    phone: str = Field(min_length=1, max_length=24, description="International (+256...) or local (0...) number")
    consent: bool = Field(description="The person agreed to receive FairPrice SMS")


def normalize_phone(raw: str, country_code: str) -> str:
    """'060 602 3950' -> '+27606023950' (with country code +27); international numbers pass through."""
    number = "".join(ch for ch in raw.strip() if ch.isdigit() or ch == "+")
    if number.startswith("00"):
        number = "+" + number[2:]
    elif number.startswith("0"):
        number = country_code + number[1:]
    elif not number.startswith("+"):
        number = "+" + number
    if not re.fullmatch(E164, number):
        raise HTTPException(422, f"'{raw}' is not a valid phone number")
    return number


def _contact(c: SmsContact) -> dict:
    return {"id": c.id, "name": c.name, "phone": c.phone}


@router.get("/contacts", summary="Saved SMS update recipients")
def list_contacts(db: DbSession, settings: AppSettings, x_admin_token: Annotated[str | None, Header()] = None):
    secure_admin(settings, x_admin_token)
    return {"contacts": [_contact(c) for c in db.scalars(select(SmsContact).order_by(SmsContact.name))],
            "country_code": settings.sms_default_country_code}


@router.post("/contacts", status_code=201, summary="Save an SMS update recipient (requires their consent)")
def add_contact(body: ContactIn, db: DbSession, settings: AppSettings,
                x_admin_token: Annotated[str | None, Header()] = None):
    secure_admin(settings, x_admin_token)
    if not body.consent:
        raise HTTPException(422, "Only save people who agreed to receive FairPrice SMS")
    phone = normalize_phone(body.phone, settings.sms_default_country_code)
    contact = db.scalar(select(SmsContact).where(SmsContact.phone == phone))
    if contact:
        contact.name = body.name.strip()
    else:
        contact = SmsContact(name=body.name.strip(), phone=phone)
        db.add(contact)
    db.commit()
    return _contact(contact)


@router.delete("/contacts/{contact_id}", status_code=204, summary="Remove a saved SMS update recipient")
def delete_contact(contact_id: int, db: DbSession, settings: AppSettings,
                   x_admin_token: Annotated[str | None, Header()] = None):
    secure_admin(settings, x_admin_token)
    contact = db.get(SmsContact, contact_id)
    if contact:
        db.delete(contact)
        db.commit()
    return Response(status_code=204)


@router.get("/staff-key", include_in_schema=False)
def staff_key(request: Request, settings: AppSettings, response: Response):
    """Fill in the staff key on the kiosk machine itself (local environment, loopback requests only)."""
    # Requests through a tunnel or proxy (ngrok, Cloudflare...) also arrive from 127.0.0.1; never give them the key.
    proxied = any(h in request.headers for h in ("x-forwarded-for", "x-forwarded-host", "forwarded", "x-real-ip",
                                                   "cf-connecting-ip", "ngrok-skip-browser-warning", "x-original-host"))
    if (settings.environment != "local" or proxied or not request.client
            or request.client.host not in {"127.0.0.1", "::1"}):
        raise HTTPException(404)
    response.headers["Cache-Control"] = "no-store"
    return {"key": settings.admin_token}


@router.post("/farmers", summary="SMS farmers a simple price list: vegetables, fruits, grains/crops")
def sms_farmers(body: FarmerUpdateIn, db: DbSession, settings: AppSettings, response: Response,
                x_admin_token: Annotated[str | None, Header()] = None):
    secure_admin(settings, x_admin_token)
    response.headers["Cache-Control"] = "no-store"
    update = farmer_update(db, body.categories, body.language)
    result = {"mode": _mode(settings, body.dry_run), "text": update["sms"], "characters": len(update["sms"]),
              "update": update, "deliveries": []}
    if result["mode"] == "dry_run":
        return result
    if not body.consent_confirmed:
        raise HTTPException(422, "consent_confirmed must be true to send")
    for phone in dict.fromkeys(body.phones):
        result["deliveries"] += _deliver(db, settings, update["sms"], to=phone)
    if body.group:
        result["deliveries"] += _deliver(db, settings, update["sms"], group=body.group)
    return result


@router.post("/buyers", summary="SMS reviewed buyers/suppliers where their crop and grade is traded now")
def sms_buyers(body: BuyerUpdateIn, db: DbSession, settings: AppSettings, response: Response,
               x_admin_token: Annotated[str | None, Header()] = None):
    secure_admin(settings, x_admin_token)
    response.headers["Cache-Control"] = "no-store"
    query = select(BuyerListing).where(BuyerListing.status == "active", BuyerListing.expires_at > utcnow(),
                                       BuyerListing.phone.is_not(None))
    if body.crop:
        query = query.where(BuyerListing.crop == body.crop)
    mode = _mode(settings, body.dry_run)
    messages = []
    for listing in db.scalars(query.order_by(BuyerListing.name)):
        update = buyer_update(db, listing, body.language)
        entry = {"buyer_id": listing.id, "name": listing.name, "phone": listing.phone,
                 "text": update["sms"], "update": update, "deliveries": []}
        if mode == "send":
            entry["deliveries"] = _deliver(db, settings, update["sms"], to=listing.phone)
        messages.append(entry)
    return {"mode": mode, "buyers": len(messages), "messages": messages,
            "notice": "Only active, staff-reviewed buyers who published a phone number are messaged."}
