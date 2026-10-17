"""
Look up prices from the trained model's outputs, in the terminal.

Run ml/ingest_wfp.py and ml/train.py first. Then, from the repo root:

    python ml/show_prices.py                         # one price per product (Northern Uganda)
    python ml/show_prices.py --crop beans            # beans in every northern market
    python ml/show_prices.py --crop beans --market gulu          # Gulu beans, last 12 months + forecast
    python ml/show_prices.py --crop maize --market lira --months 24
    python ml/show_prices.py --crop beans --core-only  # only Acholi and Lango markets

Products: beans, maize, sorghum, millet, cassava_fresh, leafy_vegetables
"""

import argparse
import json
import sys

import pandas as pd

import config


def need(path, step):
    if not path.exists():
        sys.exit(f"Missing {path}. Run {step} first.")


def load_factors():
    need(config.MARKET_FACTORS_JSON, "python ml/train.py")
    return json.loads(config.MARKET_FACTORS_JSON.read_text())["factors"]


def show_overview(core_only):
    need(config.CROP_PRICES_JSON, "python ml/train.py")
    data = json.loads(config.CROP_PRICES_JSON.read_text())
    print(f"\nNorthern Uganda MARKET prices per product (UGX/kg). Data up to {data['data_end']}.")
    print(f"Source: {data['source']}\n")
    rows = []
    for crop, c in data["crops"].items():
        rows.append({
            "product": c["crop_name"],
            "id": crop,
            "market_price": f"{c['market_price']:,.0f}",
            "forecast": f"{c['market_price_forecast']:,.0f} ({c['forecast_month']})",
            "retail_ref": f"{c['observed_retail_price']:,.0f}",
            "factor": f"x{c['market_factor']:.3f} {c['market_factor_basis']}",
            "markets": c["markets_used"],
            "note": f"stale, latest {c['latest_data_month']}" if c.get("stale") else "",
        })
    print(pd.DataFrame(rows).to_string(index=False))
    print("\nmarket_price = retail price x factor (median across markets).")
    print("How the factors were set: ml/artifacts/market_price_factors.json")
    print("See one product by market:  python ml/show_prices.py --crop beans")


def show_crop(crop, core_only):
    need(config.SNAPSHOT_CSV, "python ml/train.py")
    snap = pd.read_csv(config.SNAPSHOT_CSV)
    g = snap[snap["crop"] == crop]
    if core_only:
        g = g[g["core_area"]]
    if g.empty:
        sys.exit(f"No prices for '{crop}'. Products: {', '.join(config.CROPS)}")
    table = g[["market", "sub_region", "market_price", "market_price_forecast",
               "forecast_month", "change_pct", "observed_price", "observed_price_type",
               "last_month", "stale"]].copy()
    for col in ["market_price", "market_price_forecast", "observed_price"]:
        table[col] = table[col].map("{:,.0f}".format)
    table["stale"] = table["stale"].map({True: "stale", False: ""})
    table = table.rename(columns={"observed_price": "observed", "observed_price_type": "type",
                                  "market_price_forecast": "forecast"})
    print(f"\n{config.CROP_NAMES[crop]} MARKET prices by market (UGX/kg):\n")
    print(table.to_string(index=False))
    print(f"\nHistory for one market:  python ml/show_prices.py --crop {crop} --market gulu")


def show_history(crop, market, months):
    need(config.PROCESSED_FILE, "python ml/ingest_wfp.py")
    hist = pd.read_csv(config.PROCESSED_FILE, parse_dates=["month"])
    h = hist[(hist["crop"] == crop) & hist["market"].str.lower().str.contains(market.lower())]
    if h.empty:
        names = sorted(hist.loc[hist["crop"] == crop, "market"].unique())
        sys.exit(f"No {crop} prices for market '{market}'. Markets: {', '.join(names)}")

    factors = load_factors()
    snap = pd.read_csv(config.SNAPSHOT_CSV) if config.SNAPSHOT_CSV.exists() else None
    for (mkt, ptype), g in h.groupby(["market", "pricetype"]):
        f = 1.0 if (ptype == "Wholesale" or config.FINAL_PRICE_BASIS == "retail") \
            else factors[crop]["factor"]
        g = g.sort_values("month").tail(months)
        print(f"\n{config.CROP_NAMES[crop]} in {mkt}, UGX/kg (from {ptype} x {f:.3f}), "
              f"last {len(g)} months:")
        print(f"  month     market  ({ptype.lower()})")
        for r in g.itertuples():
            print(f"  {r.month:%Y-%m}  {r.price * f:>8,.0f}  ({r.price:,.0f})")
        if snap is not None:
            s = snap[(snap["crop"] == crop) & (snap["market"] == mkt)
                     & (snap["observed_price_type"] == ptype)]
            if len(s):
                s = s.iloc[0]
                note = "  (stale series)" if s["stale"] else ""
                print(f"  {s['forecast_month']}  {s['market_price_forecast']:>8,.0f}  <- forecast "
                      f"({s['change_pct']:+.1f}%, {s['forecast_method']}){note}")


def main():
    parser = argparse.ArgumentParser(description="Show FairPrice market prices.")
    parser.add_argument("--crop", choices=config.CROPS, help="Product id")
    parser.add_argument("--market", help="Market name or part of it, e.g. gulu, lira, palabek")
    parser.add_argument("--months", type=int, default=12, help="Months of history (with --market)")
    parser.add_argument("--core-only", action="store_true", help="Only Acholi and Lango markets")
    args = parser.parse_args()

    if args.crop and args.market:
        show_history(args.crop, args.market, args.months)
    elif args.crop:
        show_crop(args.crop, args.core_only)
    else:
        show_overview(args.core_only)


if __name__ == "__main__":
    main()
