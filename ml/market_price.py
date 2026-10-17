"""
Turn WFP retail prices into market prices.

Why: almost all WFP prices for Northern Uganda are RETAIL prices (what a shopper
pays a stall in town). A farmer or group selling produce at the market sells at the
MARKET (wholesale) level, which is lower, because the retailer adds a markup.

How: WFP recorded BOTH retail and wholesale prices for beans and maize in Lira,
for the same months, over 10+ years. For each of those months we take
    ratio = wholesale price / retail price
and use the MEDIAN ratio per crop (the median ignores the odd extreme month).

    market price = retail price x factor

  - Beans and maize: factor measured from Lira (data, not a guess).
  - Other crops: no wholesale data exists, so we use the median ratio across all
    measured months (beans + maize together) and label it "assumed".
  - Rows that already are wholesale prices are used as they are (factor 1.0).

Set config.FINAL_PRICE_BASIS = "retail" to switch the final price back to retail.
"""

import pandas as pd

import config


def compute_factors(data):
    """Median wholesale/retail ratio per crop, from months where both were recorded."""
    pairs = (data.pivot_table(index=["crop", "market", "month"], columns="pricetype",
                              values="price", aggfunc="median")
                 .dropna(subset=["Retail", "Wholesale"])
                 .reset_index())
    pairs["ratio"] = pairs["Wholesale"] / pairs["Retail"]

    factors = {}
    measured = pairs.groupby("crop")
    for crop, g in measured:
        if len(g) < config.MIN_MONTHS_FOR_FACTOR:
            continue
        factors[crop] = {
            "factor": round(float(g["ratio"].median()), 3),
            "basis": "measured",
            "months_compared": int(len(g)),
            "markets": sorted(g["market"].unique().tolist()),
            "period": f"{g['month'].min():%Y-%m} to {g['month'].max():%Y-%m}",
            "note": "median of wholesale/retail for the same market and month",
        }

    pooled = pairs[pairs["crop"].isin(factors)]
    fallback = {
        "factor": round(float(pooled["ratio"].median()), 3) if len(pooled) else None,
        "basis": "assumed",
        "months_compared": int(len(pooled)),
        "markets": sorted(pooled["market"].unique().tolist()),
        "period": (f"{pooled['month'].min():%Y-%m} to {pooled['month'].max():%Y-%m}"
                   if len(pooled) else ""),
        "note": "no wholesale data for this crop; uses the median ratio of "
                + " and ".join(config.CROP_NAMES[c] for c in factors) + " combined",
    }
    for crop in config.CROPS:
        factors.setdefault(crop, dict(fallback))
    return factors


def add_market_prices(snap, factors):
    """Add the final market price columns to the snapshot."""
    s = snap.copy()
    retail_basis = config.FINAL_PRICE_BASIS == "retail"
    is_wholesale = s["pricetype"] == "Wholesale"

    s["market_factor"] = s["crop"].map(lambda c: factors[c]["factor"])
    s["market_factor_basis"] = s["crop"].map(lambda c: factors[c]["basis"])
    s.loc[is_wholesale, "market_factor"] = 1.0
    s.loc[is_wholesale, "market_factor_basis"] = "observed wholesale"
    if retail_basis:
        s["market_factor"] = 1.0
        s["market_factor_basis"] = "retail (FINAL_PRICE_BASIS = retail)"

    s["market_price"] = (s["last_price"] * s["market_factor"]).round(0)
    s["market_price_forecast"] = (s["forecast_price"] * s["market_factor"]).round(0)
    return s.rename(columns={"last_price": "observed_price",
                             "forecast_price": "observed_forecast",
                             "pricetype": "observed_price_type"})
