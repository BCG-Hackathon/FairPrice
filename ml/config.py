"""Shared settings for the FairPrice ML pipeline (Northern Uganda only)."""

from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
REPO_DIR = ML_DIR.parent
RAW_DIR = ML_DIR / "data" / "raw"
PROCESSED_DIR = ML_DIR / "data" / "processed"
ARTIFACTS_DIR = ML_DIR / "artifacts"

RAW_FILE_NAME = "wfp_food_prices_uga.csv"
PROCESSED_FILE = PROCESSED_DIR / "prices_monthly.csv"
MODEL_FILE = ARTIFACTS_DIR / "model.pkl"
METRICS_FILE = ARTIFACTS_DIR / "metrics.json"
SNAPSHOT_CSV = ARTIFACTS_DIR / "price_snapshot.csv"
SNAPSHOT_JSON = ARTIFACTS_DIR / "price_snapshot.json"
CROP_PRICES_JSON = ARTIFACTS_DIR / "crop_prices.json"
BACKTEST_CSV = ARTIFACTS_DIR / "backtest_predictions.csv"
MARKET_FACTORS_JSON = ARTIFACTS_DIR / "market_price_factors.json"

SOURCE = "WFP VAM food prices (HDX): https://data.humdata.org/dataset/wfp-food-prices-for-uganda"

# Northern Uganda districts as they appear in the WFP file's `admin1` column.
# (Match on admin1 exactly; matching on admin2 pulled in Iganga via "Kigulu".)
SUB_REGION_BY_DISTRICT = {
    "Gulu": "Acholi",
    "Lamwo": "Acholi",
    "Lira": "Lango",
    "Arua": "West Nile",
    "Adjumani": "West Nile",
    "Koboko": "West Nile",
    "Moyo": "West Nile",
    "Yumbe": "West Nile",
    "Abim": "Karamoja",
    "Amudat": "Karamoja",
    "Kaabong": "Karamoja",
    "Kotido": "Karamoja",
    "Moroto": "Karamoja",
    "Nakapiripirit": "Karamoja",
    "Napak": "Karamoja",
}
# Clara's area. Used to flag rows in the outputs; all northern data is used for training.
CORE_SUB_REGIONS = ["Acholi", "Lango"]

# Farm products farmers sell raw, with usable Northern Uganda data.
# WFP commodity name -> our crop id. "Maize" and "Maize (white)" are the same grain.
CROP_BY_COMMODITY = {
    "Beans": "beans",
    "Maize (white)": "maize",
    "Maize": "maize",
    "Sorghum": "sorghum",
    "Millet": "millet",
    "Cassava (fresh)": "cassava_fresh",
    "Leafy vegetables": "leafy_vegetables",
}
CROP_NAMES = {
    "beans": "Beans",
    "maize": "Maize",
    "sorghum": "Sorghum",
    "millet": "Millet",
    "cassava_fresh": "Cassava (fresh)",
    "leafy_vegetables": "Leafy vegetables",
}
CROPS = list(CROP_NAMES)
PRICE_TYPES = ["Retail", "Wholesale"]
SUB_REGIONS = ["Acholi", "Lango", "West Nile", "Karamoja"]

# Backtest / snapshot settings
TEST_MONTHS = 12          # hold out the last 12 months for the honest test
STALE_AFTER_MONTHS = 6    # series with no price in the last 6 months are marked stale

# Final price shown to users. "market" = the price produce sells for at the market
# (wholesale level, see market_price.py). "retail" = the shop price WFP records.
FINAL_PRICE_BASIS = "market"
MIN_MONTHS_FOR_FACTOR = 24  # need 2+ years of paired retail/wholesale months to trust a factor
