"""Lookups for crops, markets and kiosks, including free-text matching for SMS keywords."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.i18n import CATALOGS
from app.models import Category, Crop, Kiosk, Market

# Extra spellings people type by SMS (codes and translated names are matched automatically).
CROP_ALIASES: dict[str, str] = {
    "CORN": "maize",
    "MATOOKE": "banana",
    "BANANAS": "banana",
    "AVOCADOS": "avocado",
    "TOMATOES": "tomato",
    "MANGOES": "mango",
    "BEAN": "beans",
}


def list_crops(db: Session, category: Category | None = None) -> list[Crop]:
    stmt = select(Crop).order_by(Crop.sort_order, Crop.code)
    if category:
        stmt = stmt.where(Crop.category == category)
    return list(db.scalars(stmt))


def list_markets(db: Session) -> list[Market]:
    return list(db.scalars(select(Market).order_by(Market.sort_order, Market.code)))


def list_kiosks(db: Session) -> list[Kiosk]:
    return list(db.scalars(select(Kiosk).order_by(Kiosk.code)))


def get_crop(db: Session, code: str) -> Crop | None:
    return db.scalar(select(Crop).where(Crop.code == code.lower()))


def get_market(db: Session, code: str) -> Market | None:
    return db.scalar(select(Market).where(Market.code == code.upper()))


def get_kiosk(db: Session, code: str) -> Kiosk | None:
    return db.scalar(select(Kiosk).where(Kiosk.code == code.upper()))


def match_crop(db: Session, text: str) -> Crop | None:
    """Match a crop by code, alias, or its name in any supported language."""
    word = text.strip().upper()
    code = CROP_ALIASES.get(word)
    if code is None:
        for catalog in CATALOGS.values():
            for key, value in catalog.items():
                if key.startswith("crop.") and value.upper() == word:
                    code = key.removeprefix("crop.")
                    break
            if code:
                break
    return get_crop(db, code or word)


def match_market(db: Session, text: str) -> Market | None:
    word = text.strip().upper()
    market = get_market(db, word)
    if market:
        return market
    return next((m for m in list_markets(db) if m.name.upper().startswith(word)), None)
