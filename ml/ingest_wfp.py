"""
Step 1 of the pipeline: clean the WFP Uganda CSV into one monthly price table.

Keeps Northern Uganda markets and the six farm products in config.CROP_BY_COMMODITY,
in UGX per kg. Output: ml/data/processed/prices_monthly.csv

Run from the repo root:
    python ml/ingest_wfp.py
    python ml/ingest_wfp.py --input path/to/wfp_food_prices_uga.csv
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import config


def find_input(explicit):
    """Use --input if given, else ml/data/raw/, else the repo root."""
    candidates = [Path(explicit)] if explicit else [
        config.RAW_DIR / config.RAW_FILE_NAME,
        config.REPO_DIR / config.RAW_FILE_NAME,
    ]
    for path in candidates:
        if path.exists():
            return path
    sys.exit("Could not find the WFP CSV. Download it from\n"
             "  https://data.humdata.org/dataset/wfp-food-prices-for-uganda\n"
             f"and save it as {config.RAW_DIR / config.RAW_FILE_NAME}")


def load_raw(path):
    df = pd.read_csv(path, low_memory=False)
    # HDX files have a second header row of tags like "#date": drop it.
    df = df[~df["date"].astype(str).str.startswith("#")]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    for col in ["latitude", "longitude"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["date", "price"])


def drop_outliers(df, max_ratio=4.0):
    """Drop prices more than 4x above or below their series' rolling median."""
    keys = ["crop", "market", "pricetype"]
    df = df.sort_values(keys + ["month"])
    rolling_median = (df.groupby(keys)["price"]
                        .transform(lambda s: s.rolling(7, center=True, min_periods=3).median()))
    ratio = df["price"] / rolling_median
    bad = (ratio > max_ratio) | (ratio < 1 / max_ratio)
    if bad.any():
        print(f"Dropped {int(bad.sum())} outlier prices (more than {max_ratio}x off the local median).")
    return df[~bad]


def main():
    parser = argparse.ArgumentParser(description="Clean WFP Uganda prices for Northern Uganda.")
    parser.add_argument("--input", help="Path to wfp_food_prices_uga.csv")
    parser.add_argument("--output", default=str(config.PROCESSED_FILE))
    args = parser.parse_args()

    path = find_input(args.input)
    raw = load_raw(path)
    print(f"Read {len(raw):,} rows from {path}")

    df = raw[raw["admin1"].isin(config.SUB_REGION_BY_DISTRICT)
             & raw["commodity"].isin(config.CROP_BY_COMMODITY)
             & raw["pricetype"].isin(config.PRICE_TYPES)
             & (raw["unit"].str.upper() == "KG")
             & (raw["currency"] == "UGX")
             & (raw["price"] > 0)].copy()
    if "priceflag" in df.columns:
        df = df[df["priceflag"].isin(["actual", "aggregate"])]

    df["crop"] = df["commodity"].map(config.CROP_BY_COMMODITY)
    df["sub_region"] = df["admin1"].map(config.SUB_REGION_BY_DISTRICT)
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()

    # One price per crop, market, price type and month (median if several).
    monthly = (df.groupby(["month", "crop", "market", "admin1", "sub_region", "pricetype"],
                          as_index=False)
                 .agg(price=("price", "median"),
                      latitude=("latitude", "first"),
                      longitude=("longitude", "first")))
    monthly = drop_outliers(monthly)
    monthly["price"] = monthly["price"].round(2)
    monthly["core_area"] = monthly["sub_region"].isin(config.CORE_SUB_REGIONS)
    monthly = monthly.rename(columns={"admin1": "district"})
    monthly = monthly.sort_values(["crop", "market", "pricetype", "month"])

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(out, index=False)

    summary = (monthly.groupby(["crop", "pricetype"])
                      .agg(rows=("price", "size"), markets=("market", "nunique"),
                           first=("month", "min"), last=("month", "max")))
    summary["first"] = summary["first"].dt.strftime("%Y-%m")
    summary["last"] = summary["last"].dt.strftime("%Y-%m")
    print(f"\nSaved {len(monthly):,} monthly prices to {out}\n")
    print(summary.to_string())


if __name__ == "__main__":
    main()
