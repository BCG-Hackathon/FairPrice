"""Pure pricing rules. No I/O, so they are easy to test and explain to judges.

fair farm-gate price/kg = market price x (1 - trader margin) - transport cost/kg
"""

from dataclasses import dataclass
from enum import StrEnum

from app.models import Grade


class Trend(StrEnum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    NEW = "new"  # no previous price to compare with


class Verdict(StrEnum):
    FAIR = "fair"
    LOW = "low"
    VERY_LOW = "very_low"


def grade_price(price_a: float, grade: Grade, grade_b_factor: float) -> float:
    return price_a if grade == Grade.A else price_a * grade_b_factor


def change_pct(current: float, previous: float | None) -> float | None:
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)


def trend_of(pct: float | None, flat_band_pct: float) -> Trend:
    if pct is None:
        return Trend.NEW
    if abs(pct) < flat_band_pct:
        return Trend.FLAT
    return Trend.UP if pct > 0 else Trend.DOWN


def fair_farm_gate_price(market_price: float, transport_per_kg: float, trader_margin: float) -> float:
    """What a fair buyer could pay at the farm and still profit by reselling at the market."""
    return max(0.0, market_price * (1 - trader_margin) - transport_per_kg)


def self_sell_net(market_price: float, transport_per_kg: float) -> float:
    """What the farmer keeps per kg by transporting and selling at the market themselves."""
    return max(0.0, market_price - transport_per_kg)


@dataclass(frozen=True)
class OfferAssessment:
    verdict: Verdict
    fair_price: float
    gap_per_kg: float  # positive = farmer would lose this much per kg by accepting
    pct_of_fair: float


def assess_offer(offer_per_kg: float, fair_price: float, low_threshold: float) -> OfferAssessment:
    if fair_price <= 0:
        return OfferAssessment(Verdict.FAIR, fair_price, 0.0, 100.0)
    ratio = offer_per_kg / fair_price
    if ratio >= 1:
        verdict = Verdict.FAIR
    elif ratio >= low_threshold:
        verdict = Verdict.LOW
    else:
        verdict = Verdict.VERY_LOW
    return OfferAssessment(
        verdict=verdict,
        fair_price=fair_price,
        gap_per_kg=max(0.0, fair_price - offer_per_kg),
        pct_of_fair=round(ratio * 100, 1),
    )
