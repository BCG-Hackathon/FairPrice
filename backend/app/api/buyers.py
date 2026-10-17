"""Buyer registration is opt-in; publication requires kiosk review."""
import hashlib
import secrets
from datetime import timedelta
from typing import Annotated, Literal
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from app.deps import DbSession, AppSettings
from app.models import BuyerListing, utcnow
from app.services.published import CROP_META

router = APIRouter(prefix="/api/buyers", tags=["buyer directory"])


def secure_admin(settings, token):
    if len(settings.admin_token)<16 or settings.admin_token in {"", "change-me"} or not token or not secrets.compare_digest(token, settings.admin_token):
        raise HTTPException(401, "Kiosk staff authentication required. Configure a strong ADMIN_TOKEN; default tokens are rejected.")


class Registration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=80)
    location: str = Field(min_length=2, max_length=100)
    crop: str = Field(max_length=32)
    grade: Literal["A", "B", "C"]
    phone: str | None = Field(default=None, pattern=r"^\+[1-9][0-9]{7,14}$")
    consent_to_listing: Literal[True]
    publish_phone: bool = False

    @field_validator("crop")
    @classmethod
    def supported(cls, value):
        if value not in CROP_META:
            raise ValueError("Unsupported crop")
        return value


def public_row(row):
    return {"id": row.id, "name": row.name, "location": row.location, "crop": row.crop,
            "grade": row.grade, "phone": row.phone, "contact_method": "phone" if row.phone else "kiosk",
            "status": row.status, "expires_at": row.expires_at.isoformat(), "review_notice": "Kiosk-reviewed listing; buyer identity and ability to pay are not guaranteed."}


@router.get("")
def buyers(db: DbSession, crop: str, grade: Literal["A", "B", "C"]):
    if crop not in CROP_META:
        raise HTTPException(404, "Crop unavailable")
    rows = db.scalars(select(BuyerListing).where(BuyerListing.crop == crop, BuyerListing.grade == grade,
                       BuyerListing.status == "active", BuyerListing.expires_at > utcnow()).order_by(BuyerListing.name))
    return {"crop": crop, "grade": grade, "buyers": [public_row(r) for r in rows],
            "notice": "Prices are negotiated directly. No price, sale, payment or guaranteed demand is recorded here."}


@router.post("/register", status_code=201)
def register(body: Registration, db: DbSession, settings: AppSettings, request: Request):
    # Hash client address with the server secret; do not retain the raw address or a hidden phone.
    key = hashlib.sha256((settings.admin_token + (request.client.host if request.client else "local")).encode()).hexdigest()
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    count = db.scalar(select(func.count()).select_from(BuyerListing).where(BuyerListing.registration_key == key, BuyerListing.created_at >= today))
    if count >= settings.buyer_registration_daily_limit:
        raise HTTPException(429, "Daily registration limit reached. Ask kiosk staff for help.")
    listing = BuyerListing(name=body.name, location=body.location, crop=body.crop, grade=body.grade,
        phone=body.phone if body.publish_phone else None, status="pending", expires_at=utcnow()+timedelta(days=30), registration_key=key)
    db.add(listing); db.commit()
    return {"id": listing.id, "status": "pending", "message": "Registration saved for kiosk review. It is not public yet."}


@router.get("/pending")
def pending(db: DbSession, settings: AppSettings, x_admin_token: Annotated[str | None, Header()] = None):
    secure_admin(settings, x_admin_token)
    return {"buyers": [public_row(r) for r in db.scalars(select(BuyerListing).where(BuyerListing.status == "pending").order_by(BuyerListing.created_at))]}


@router.get("/manage")
def manage(db: DbSession, settings: AppSettings, x_admin_token: Annotated[str | None, Header()] = None):
    secure_admin(settings, x_admin_token)
    return {"buyers": [public_row(r) for r in db.scalars(select(BuyerListing).where(BuyerListing.status.in_(["pending","active"])).order_by(BuyerListing.created_at))]}


class Review(BaseModel):
    action: Literal["approve", "reject", "withdraw"]


@router.post("/{listing_id}/review")
def review(listing_id: int, body: Review, db: DbSession, settings: AppSettings,
           x_admin_token: Annotated[str | None, Header()] = None):
    secure_admin(settings, x_admin_token)
    row = db.get(BuyerListing, listing_id)
    if row is None:
        raise HTTPException(404, "Listing not found")
    row.status = {"approve": "active", "reject": "rejected", "withdraw": "withdrawn"}[body.action]
    row.reviewed_at = utcnow()
    if body.action == "approve":
        row.expires_at = utcnow()+timedelta(days=30)
    db.commit()
    return {"id": row.id, "status": row.status}
