"""Market comparison and Offer Check, built on snapshots + transport + pricing rules."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import Settings
from app.i18n import crop_name, format_ugx, t
from app.models import Crop, Grade, Kiosk, Language, Market, PriceSnapshot
from app.services import pricing
from app.services.snapshot import get_snapshot, list_snapshots
from app.services.transport import TransportProvider


@dataclass(frozen=True)
class MarketOption:
    market: Market
    snapshot: PriceSnapshot
    market_price: float
    transport_ugx_per_kg: float
    distance_km: float
    fair_farm_gate_price: float
    self_sell_net_per_kg: float


@dataclass(frozen=True)
class OfferCheck:
    crop: Crop
    grade: Grade
    reference: MarketOption
    best: MarketOption
    offer_per_kg: float
    quantity_kg: float
    assessment: pricing.OfferAssessment

    @property
    def total_loss(self) -> float:
        return self.assessment.gap_per_kg * self.quantity_kg


def market_option(
    snapshot: PriceSnapshot, grade: Grade, origin: Kiosk, transport: TransportProvider, settings: Settings
) -> MarketOption:
    price = snapshot.price_a if grade == Grade.A else snapshot.price_b
    estimate = transport.estimate(origin, snapshot.market)
    return MarketOption(
        market=snapshot.market,
        snapshot=snapshot,
        market_price=price,
        transport_ugx_per_kg=estimate.cost_ugx_per_kg,
        distance_km=estimate.distance_km,
        fair_farm_gate_price=round(
            pricing.fair_farm_gate_price(price, estimate.cost_ugx_per_kg, settings.fair_trader_margin)
        ),
        self_sell_net_per_kg=round(pricing.self_sell_net(price, estimate.cost_ugx_per_kg)),
    )


def compare_markets(
    db: Session, crop: Crop, grade: Grade, origin: Kiosk, transport: TransportProvider, settings: Settings
) -> list[MarketOption]:
    """All markets with a price for this crop, best farm-gate price first."""
    options = [
        market_option(s, grade, origin, transport, settings)
        for s in list_snapshots(db)
        if s.crop_id == crop.id
    ]
    return sorted(options, key=lambda o: o.fair_farm_gate_price, reverse=True)


def check_offer(
    db: Session,
    *,
    crop: Crop,
    grade: Grade,
    offer_per_kg: float,
    quantity_kg: float,
    origin: Kiosk,
    market: Market | None,
    transport: TransportProvider,
    settings: Settings,
) -> OfferCheck | None:
    """Compare a broker's offer with the fair farm-gate price.

    The reference market is the one the farmer names, else the best option.
    Returns None when we have no price for this crop.
    """
    options = compare_markets(db, crop, grade, origin, transport, settings)
    if not options:
        return None
    best = options[0]
    reference = best
    if market is not None:
        snapshot = get_snapshot(db, market.id, crop.id)
        if snapshot is None:
            return None
        reference = market_option(snapshot, grade, origin, transport, settings)
    assessment = pricing.assess_offer(offer_per_kg, reference.fair_farm_gate_price, settings.offer_low_threshold)
    return OfferCheck(
        crop=crop,
        grade=grade,
        reference=reference,
        best=best,
        offer_per_kg=offer_per_kg,
        quantity_kg=quantity_kg,
        assessment=assessment,
    )


def offer_message(lang: Language | None, result: OfferCheck) -> str:
    """Plain-text verdict for SMS and the kiosk, e.g. 'Offer 700 for Maize A is LOW. ...'."""
    text = t(
        lang,
        "offer.reply",
        offer=format_ugx(result.offer_per_kg),
        crop=crop_name(lang, result.crop.code),
        grade=result.grade.value,
        verdict=t(lang, f"verdict.{result.assessment.verdict.value}"),
        floor=format_ugx(result.reference.fair_farm_gate_price),
        market=result.reference.market.name,
        market_price=format_ugx(result.reference.market_price),
    )
    if result.total_loss > 0:
        text += t(lang, "offer.loss", qty=format_ugx(result.quantity_kg), loss=format_ugx(result.total_loss))
    return text
