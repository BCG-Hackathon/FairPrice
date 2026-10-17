"""One deterministic price policy shared by kiosk and SMS. No LLM prices."""
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite

GRADE_FACTORS = {"A": Decimal("1.04"), "B": Decimal("1"), "C": Decimal("0.945")}
POLICY_VERSION = "user-policy-2026-10-17"


def grade_prices(base_price):
    if isinstance(base_price, bool) or not isfinite(float(base_price)) or float(base_price) <= 0:
        raise ValueError("Base price must be a finite positive number")
    price = Decimal(str(base_price))
    return {grade: int((price * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            for grade, factor in GRADE_FACTORS.items()}
