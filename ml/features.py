"""
Step 2: turn the monthly price table into model features.

The model predicts next month's price change in log terms:
    target = log(price next month) - log(price this month)
so one model works across crops with very different price levels.
The forecast price is then: this month's price x exp(predicted change).
"""

import numpy as np
import pandas as pd

import config

SERIES_KEYS = ["crop", "market", "district", "sub_region", "pricetype"]
CATEGORICAL = ["crop", "market", "sub_region", "pricetype"]
NUMERIC = [
    "log_price", "month_sin", "month_cos",
    "ret_1", "ret_2", "ret_3", "ret_6", "ret_12",
    "dev_ma3", "dev_ma6", "dev_ma12", "vol_6",
    "seasonal_next", "crop_avg_ret_1", "history_months",
]
FEATURES = CATEGORICAL + NUMERIC


def load_processed(path=config.PROCESSED_FILE):
    df = pd.read_csv(path, parse_dates=["month"])
    return df


def build_panel(df):
    """One row per series per calendar month (gaps left as NaN)."""
    parts = []
    for keys, g in df.groupby(SERIES_KEYS):
        g = g.set_index("month").sort_index()
        months = pd.date_range(g.index.min(), g.index.max(), freq="MS")
        g = g.reindex(months)
        g.index.name = "month"
        for k, v in zip(SERIES_KEYS, keys):
            g[k] = v
        for col in ["latitude", "longitude", "core_area"]:
            if col in g:
                g[col] = g[col].ffill().bfill()
        parts.append(g.reset_index())
    return pd.concat(parts, ignore_index=True)


def add_features(panel):
    """Add features (known at month t) and the target (change to month t+1)."""
    p = panel.sort_values(SERIES_KEYS + ["month"]).copy()
    p["log_price"] = np.log(p["price"])
    grp = p.groupby(SERIES_KEYS, sort=False)["log_price"]

    lag = {k: grp.shift(k) for k in [1, 2, 3, 6, 11, 12]}
    p["ret_1"] = p["log_price"] - lag[1]
    p["ret_2"] = p["log_price"] - lag[2]
    p["ret_3"] = p["log_price"] - lag[3]
    p["ret_6"] = p["log_price"] - lag[6]
    p["ret_12"] = p["log_price"] - lag[12]
    # What happened from this month to next month one year ago (seasonality).
    p["seasonal_next"] = lag[11] - lag[12]

    for w in [3, 6, 12]:
        ma = grp.transform(lambda s: s.rolling(w, min_periods=max(2, w // 2)).mean())
        p[f"dev_ma{w}"] = p["log_price"] - ma
    p["vol_6"] = (p.groupby(SERIES_KEYS, sort=False)["ret_1"]
                   .transform(lambda s: s.rolling(6, min_periods=3).std()))
    p["history_months"] = p.groupby(SERIES_KEYS, sort=False)["price"].transform(
        lambda s: s.notna().cumsum())

    # Average monthly change for the same crop and price type across all northern markets.
    p["crop_avg_ret_1"] = p.groupby(["crop", "pricetype", "month"])["ret_1"].transform("mean")

    m = p["month"].dt.month
    p["month_sin"] = np.sin(2 * np.pi * m / 12)
    p["month_cos"] = np.cos(2 * np.pi * m / 12)

    p["target"] = grp.shift(-1) - p["log_price"]
    p["next_price"] = p.groupby(SERIES_KEYS, sort=False)["price"].shift(-1)
    return p


def to_model_frame(df, categories):
    """Select feature columns with fixed category levels (same at train and predict time)."""
    X = df[FEATURES].copy()
    for col in CATEGORICAL:
        X[col] = pd.Categorical(X[col], categories=categories[col])
    return X


def category_levels(df):
    return {
        "crop": config.CROPS,
        "pricetype": config.PRICE_TYPES,
        "sub_region": config.SUB_REGIONS,
        "market": sorted(df["market"].dropna().unique().tolist()),
    }


def training_rows(feat):
    """Rows where both this month's and next month's prices are real observations."""
    return feat[feat["price"].notna() & feat["target"].notna()].copy()
