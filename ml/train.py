"""
Step 3: train the price model and write the price snapshot the backend serves.

What it does:
  1. Holds out the last 12 months and checks the model against a naive baseline
     ("next month's price = this month's price"), per crop.
  2. Retrains on all data and saves ml/artifacts/model.pkl.
  3. Forecasts next month's price for every crop x market x price type and saves:
       ml/artifacts/price_snapshot.csv / .json   one row per crop, market, price type
       ml/artifacts/crop_prices.json             one price per crop for Northern Uganda
       ml/artifacts/metrics.json                 test results (MAPE vs baseline)
       ml/artifacts/market_price_factors.json    how retail was turned into market price
  All final prices are MARKET prices (see market_price.py).
  For any crop where the model does NOT beat the baseline, the snapshot uses the
  baseline instead and says so ("forecast_method": "naive"). We never claim more
  than the test shows.

Run from the repo root (after ml/ingest_wfp.py):
    python ml/train.py
"""

import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

import config
from features import (FEATURES, add_features, build_panel, category_levels,
                      load_processed, to_model_frame, training_rows)
from market_price import add_market_prices, compute_factors


def fit_model(X, y):
    model = LGBMRegressor(
        objective="l1",            # robust to odd prices
        n_estimators=400,
        learning_rate=0.03,
        num_leaves=15,
        min_child_samples=20,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        random_state=42,
        verbose=-1,
    )
    model.fit(X, y)
    return model


def ape(pred, actual):
    return np.abs(pred - actual) / actual


def score(df, pred_col):
    """Mean absolute percentage error (%) and share of forecasts within 10%."""
    e = ape(df[pred_col], df["next_price"])
    return {"mape_pct": round(float(e.mean() * 100), 2),
            "within_10pct": round(float((e <= 0.10).mean() * 100), 1)}


def evaluate(test):
    """Compare model and naive baseline, overall and per crop."""
    result = {"overall": {"rows": int(len(test)),
                          "model": score(test, "pred_price"),
                          "naive": score(test, "naive_price")},
              "by_crop": {}}
    for crop, g in test.groupby("crop"):
        m, n = score(g, "pred_price"), score(g, "naive_price")
        result["by_crop"][crop] = {"rows": int(len(g)), "model": m, "naive": n,
                                   "model_beats_naive": m["mape_pct"] < n["mape_pct"]}
    o = result["overall"]
    o["model_beats_naive"] = o["model"]["mape_pct"] < o["naive"]["mape_pct"]
    return result


def holdout_split(rows, test_months=config.TEST_MONTHS):
    last = rows["month"].max()
    cutoff = last - pd.DateOffset(months=test_months - 1)
    return rows[rows["month"] < cutoff], rows[rows["month"] >= cutoff], cutoff


def build_snapshot(feat, model, cats, use_model_for, data_end):
    """Latest real price per series, plus next month's forecast."""
    obs = feat[feat["price"].notna()]
    latest = obs.loc[obs.groupby(["crop", "market", "pricetype"])["month"].idxmax()].copy()

    pred_change = model.predict(to_model_frame(latest, cats))
    model_price = latest["price"] * np.exp(pred_change)
    latest["forecast_method"] = np.where(latest["crop"].isin(use_model_for), "model", "naive")
    latest["forecast_price"] = np.where(latest["forecast_method"] == "model",
                                        model_price, latest["price"]).round(0)

    months_old = ((data_end.year - latest["month"].dt.year) * 12
                  + (data_end.month - latest["month"].dt.month))
    snap = pd.DataFrame({
        "crop": latest["crop"],
        "crop_name": latest["crop"].map(config.CROP_NAMES),
        "market": latest["market"],
        "district": latest["district"],
        "sub_region": latest["sub_region"],
        "core_area": latest["sub_region"].isin(config.CORE_SUB_REGIONS),
        "pricetype": latest["pricetype"],
        "unit": "UGX/kg",
        "last_price": latest["price"].round(0),
        "last_month": latest["month"].dt.strftime("%Y-%m"),
        "forecast_month": (latest["month"] + pd.DateOffset(months=1)).dt.strftime("%Y-%m"),
        "forecast_price": latest["forecast_price"],
        "change_pct": ((latest["forecast_price"] / latest["price"] - 1) * 100).round(1),
        "forecast_method": latest["forecast_method"],
        "history_months": latest["history_months"].astype(int),
        "months_since_last_price": months_old.astype(int),
        "stale": months_old > config.STALE_AFTER_MONTHS,
        "latitude": latest["latitude"],
        "longitude": latest["longitude"],
        "source": config.SOURCE,
    })
    return snap.sort_values(["crop", "core_area", "market", "pricetype"],
                            ascending=[True, False, True, True]).reset_index(drop=True)


def crop_summary(snap):
    """One headline MARKET price per crop for Northern Uganda.

    Uses retail-based rows from series updated in the last 6 months, converted to
    market prices. If a crop has none (e.g. millet), it falls back to its latest
    prices and marks the crop as stale."""
    out = {}
    for crop, g in snap.groupby("crop"):
        fresh = g[~g["stale"]]
        is_stale = fresh.empty      # e.g. millet: no northern price in the last 6 months
        g = g if is_stale else fresh
        retail = g[g["observed_price_type"] == "Retail"]
        g = retail if len(retail) else g
        core = g[g["core_area"]]
        out[crop] = {
            "crop_name": config.CROP_NAMES[crop],
            "unit": "UGX/kg",
            "price_basis": config.FINAL_PRICE_BASIS,
            "market_price": float(g["market_price"].median()),
            "market_price_forecast": float(g["market_price_forecast"].median()),
            "forecast_month": g["forecast_month"].max(),
            "market_factor": float(g["market_factor"].iloc[0]),
            "market_factor_basis": g["market_factor_basis"].iloc[0],
            "observed_retail_price": float(g["observed_price"].median()),
            "markets_used": int(g["market"].nunique()),
            "core_markets": {r.market: {"market_price": float(r.market_price),
                                        "market_price_forecast": float(r.market_price_forecast),
                                        "month": r.last_month}
                             for r in core.itertuples()},
            "forecast_method": g["forecast_method"].iloc[0],
            "stale": bool(is_stale),
            "latest_data_month": g["last_month"].max(),
        }
    return out


def main():
    config.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    data = load_processed()
    data_end = data["month"].max()
    feat = add_features(build_panel(data))
    cats = category_levels(data)
    rows = training_rows(feat)

    # 1. Honest test on the last 12 months.
    train, test, cutoff = holdout_split(rows)
    model = fit_model(to_model_frame(train, cats), train["target"])
    test = test.copy()
    test["pred_price"] = test["price"] * np.exp(model.predict(to_model_frame(test, cats)))
    test["naive_price"] = test["price"]
    metrics = evaluate(test)

    use_model_for = [c for c, r in metrics["by_crop"].items() if r["model_beats_naive"]]

    # 2. Retrain on everything for the live forecast.
    final = fit_model(to_model_frame(rows, cats), rows["target"])
    trained_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    joblib.dump({"model": final, "features": FEATURES, "categories": cats,
                 "use_model_for": use_model_for, "trained_at": trained_at,
                 "data_end": data_end.strftime("%Y-%m"), "target": "log price change, 1 month"},
                config.MODEL_FILE)

    # 3. Snapshot + per-crop prices.
    snap = build_snapshot(feat, final, cats, use_model_for, data_end)
    factors = compute_factors(data)
    config.MARKET_FACTORS_JSON.write_text(json.dumps(
        {"final_price_basis": config.FINAL_PRICE_BASIS,
         "formula": "market price = retail price x factor",
         "factors": factors}, indent=2))
    snap = add_market_prices(snap, factors)
    snap.to_csv(config.SNAPSHOT_CSV, index=False)
    payload = {"generated_at": trained_at, "data_end": data_end.strftime("%Y-%m"),
               "source": config.SOURCE, "rows": json.loads(snap.to_json(orient="records"))}
    config.SNAPSHOT_JSON.write_text(json.dumps(payload, indent=2))
    crops = crop_summary(snap)
    config.CROP_PRICES_JSON.write_text(json.dumps(
        {"generated_at": trained_at, "data_end": data_end.strftime("%Y-%m"),
         "source": config.SOURCE, "price_basis": config.FINAL_PRICE_BASIS,
         "crops": crops}, indent=2))

    metrics.update({"trained_at": trained_at, "data_end": data_end.strftime("%Y-%m"),
                    "test_from": cutoff.strftime("%Y-%m"), "train_rows": int(len(train)),
                    "all_rows": int(len(rows)), "model_used_for": use_model_for,
                    "baseline": "naive: next month's price = this month's price"})
    config.METRICS_FILE.write_text(json.dumps(metrics, indent=2))

    # Console report
    o = metrics["overall"]
    print(f"Data up to {data_end:%Y-%m}; tested on {o['rows']} forecasts from {cutoff:%Y-%m}.")
    print(f"Overall MAPE  model {o['model']['mape_pct']}%  vs  naive {o['naive']['mape_pct']}%")
    print("\nPer crop (MAPE %):")
    for crop, r in metrics["by_crop"].items():
        flag = "model" if r["model_beats_naive"] else "naive (model did not beat baseline)"
        print(f"  {config.CROP_NAMES[crop]:<18} model {r['model']['mape_pct']:>5}  "
              f"naive {r['naive']['mape_pct']:>5}  rows {r['rows']:>4}  -> use {flag}")
    print("\nMarket price factors (market price = retail price x factor):")
    for crop, f in factors.items():
        print(f"  {config.CROP_NAMES[crop]:<18} x {f['factor']:.3f}  {f['basis']:<8} "
              f"({f['months_compared']} months, {', '.join(f['markets'])}, {f['period']})")
    print(f"\nNorthern Uganda MARKET price per crop (UGX/kg, basis: {config.FINAL_PRICE_BASIS}):")
    for crop, c in crops.items():
        print(f"  {c['crop_name']:<18} market {c['market_price']:>8,.0f}  "
              f"forecast {c['forecast_month']} {c['market_price_forecast']:>8,.0f}  "
              f"(retail {c['observed_retail_price']:,.0f}, {c['markets_used']} markets)"
              + (f"  STALE: latest data {c['latest_data_month']}" if c["stale"] else ""))
    print(f"\nSaved: {config.MODEL_FILE.name}, {config.SNAPSHOT_CSV.name}, "
          f"{config.SNAPSHOT_JSON.name}, {config.CROP_PRICES_JSON.name}, "
          f"{config.METRICS_FILE.name}, {config.MARKET_FACTORS_JSON.name} in {config.ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
