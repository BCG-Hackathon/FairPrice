"""
Step 4 (optional, stronger check): rolling backtest.

For each of the last N months, train only on data BEFORE that month, forecast the
next month, and compare with what really happened. This mimics using the model
live every month. Prints MAPE per crop for the model vs two baselines:
  - naive:          next month = this month
  - seasonal naive: next month = this month x last year's change for the same months
Saves every forecast to ml/artifacts/backtest_predictions.csv (for the admin chart).

Run from the repo root (after ml/ingest_wfp.py):
    python ml/backtest.py
    python ml/backtest.py --months 24
"""

import argparse

import numpy as np
import pandas as pd

import config
from features import (add_features, build_panel, category_levels, load_processed,
                      to_model_frame, training_rows)
from train import ape, fit_model


def main():
    parser = argparse.ArgumentParser(description="Rolling-origin backtest.")
    parser.add_argument("--months", type=int, default=config.TEST_MONTHS,
                        help="How many recent months to test (default 12)")
    args = parser.parse_args()

    data = load_processed()
    feat = add_features(build_panel(data))
    cats = category_levels(data)
    rows = training_rows(feat)

    origins = sorted(rows["month"].unique())[-args.months:]
    preds = []
    for origin in origins:
        train = rows[rows["month"] < origin]
        test = rows[rows["month"] == origin].copy()
        if test.empty or len(train) < 200:
            continue
        model = fit_model(to_model_frame(train, cats), train["target"])
        test["pred_price"] = test["price"] * np.exp(model.predict(to_model_frame(test, cats)))
        preds.append(test)
        print(f"  forecast from {pd.Timestamp(origin):%Y-%m}: {len(test)} series")

    bt = pd.concat(preds, ignore_index=True)
    bt["naive_price"] = bt["price"]
    bt["seasonal_naive_price"] = bt["price"] * np.exp(bt["seasonal_next"].fillna(0))
    bt["forecast_month"] = (bt["month"] + pd.DateOffset(months=1)).dt.strftime("%Y-%m")

    def mape(g, col):
        return round(float(ape(g[col], g["next_price"]).mean() * 100), 2)

    table = (bt.groupby("crop")
               .apply(lambda g: pd.Series({
                   "rows": len(g),
                   "model_mape": mape(g, "pred_price"),
                   "naive_mape": mape(g, "naive_price"),
                   "seasonal_mape": mape(g, "seasonal_naive_price")}), include_groups=False))
    table.index = table.index.map(config.CROP_NAMES)
    table["best"] = table[["model_mape", "naive_mape", "seasonal_mape"]].idxmin(axis=1) \
        .str.replace("_mape", "")
    table.loc["ALL"] = [len(bt), mape(bt, "pred_price"), mape(bt, "naive_price"),
                        mape(bt, "seasonal_naive_price"), ""]
    table.loc["ALL", "best"] = table.loc["ALL", ["model_mape", "naive_mape",
                                                  "seasonal_mape"]].astype(float).idxmin() \
        .replace("_mape", "")

    print(f"\nRolling backtest, {len(origins)} months, MAPE % (lower is better):")
    print(table.to_string())

    out = bt[["crop", "market", "sub_region", "pricetype", "forecast_month", "price",
              "next_price", "pred_price", "naive_price", "seasonal_naive_price"]].rename(
        columns={"price": "price_this_month", "next_price": "actual_next_month"})
    out = out.round({"pred_price": 0, "naive_price": 0, "seasonal_naive_price": 0})
    config.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(config.BACKTEST_CSV, index=False)
    print(f"\nSaved {len(out)} forecasts to {config.BACKTEST_CSV}")


if __name__ == "__main__":
    main()
