import pytest

from app.models import Grade
from app.services import pricing
from app.services.pricing import Trend, Verdict


def test_fair_farm_gate_price_deducts_margin_and_transport():
    # 1,000 market price, 20% trader margin, 100/kg transport -> 700 at the farm gate
    assert pricing.fair_farm_gate_price(1000, 100, 0.20) == 700


def test_fair_farm_gate_price_never_negative():
    assert pricing.fair_farm_gate_price(100, 500, 0.20) == 0


def test_grade_b_price_uses_factor():
    assert pricing.grade_price(1000, Grade.B, 0.6) == 600
    assert pricing.grade_price(1000, Grade.A, 0.6) == 1000


@pytest.mark.parametrize(
    ("pct", "expected"),
    [(None, Trend.NEW), (0.5, Trend.FLAT), (-0.9, Trend.FLAT), (5.0, Trend.UP), (-3.0, Trend.DOWN)],
)
def test_trend_bands(pct, expected):
    assert pricing.trend_of(pct, flat_band_pct=1.0) == expected


def test_change_pct():
    assert pricing.change_pct(1100, 1000) == 10.0
    assert pricing.change_pct(1000, None) is None


@pytest.mark.parametrize(
    ("offer", "verdict"),
    [(1000, Verdict.FAIR), (900, Verdict.LOW), (850, Verdict.LOW), (300, Verdict.VERY_LOW)],
)
def test_assess_offer_verdicts(offer, verdict):
    result = pricing.assess_offer(offer, fair_price=1000, low_threshold=0.85)
    assert result.verdict == verdict
    assert result.gap_per_kg == max(0, 1000 - offer)
