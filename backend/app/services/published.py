"""Read the versioned ML snapshot; preserve each market's observation date."""
import json
from datetime import date
from pathlib import Path
from .grade_policy import grade_prices, POLICY_VERSION

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "ml" / "artifacts"
CROP_META = {
    "beans": ("Beans", "Maharagwe", "grains", "Dry beans"),
    "maize": ("Maize", "Mahindi", "grains", "Maize grain"),
    "sorghum": ("Sorghum", "Mtama", "grains", "Sorghum grain"),
    "millet": ("Millet", "Uwele", "grains", "Millet grain; variety unspecified"),
    "cassava_fresh": ("Fresh cassava", "Muhogo mbichi", "vegetables", "Fresh roots, not flour"),
    "leafy_vegetables": ("Leafy vegetables", "Mboga za majani", "vegetables", "Mixed category; species unspecified"),
}


def load_snapshot(db=None):
    if db is not None:
        from sqlalchemy import select
        from app.models import PublishedPrice
        rows = [r.payload for r in db.scalars(select(PublishedPrice))]
        if not rows:
            raise ValueError("No published records loaded in the database")
        meta = rows[0]
        return {"rows": rows, "source": meta["source"],
                "generated_at": meta["snapshot_generated_at"], "data_end": meta["snapshot_data_end"]}
    return json.loads((ARTIFACTS / "price_snapshot.json").read_text(encoding="utf-8"))


def catalogue(db=None):
    snapshot = load_snapshot(db)
    present = {r["crop"] for r in snapshot["rows"]}
    return {"source": snapshot["source"], "generated_at": snapshot["generated_at"],
            "data_end": snapshot["data_end"], "crops": [
        {"id": k, "name": v[0], "name_sw": v[1], "category": v[2], "form": v[3],
         "image": f"/assets/{k}.png",
         "markets": sorted({r["market"] for r in snapshot["rows"] if r["crop"] == k})}
        for k, v in CROP_META.items() if k in present]}


def prices(crop, market=None, today=None, db=None):
    if crop not in CROP_META:
        raise KeyError("Crop not supported by the pricing data")
    snapshot = load_snapshot(db)
    candidates = [r for r in snapshot["rows"] if r["crop"] == crop and
                  (market is None or r["market"] == market)]
    if not candidates:
        raise KeyError("No price for that crop and market")
    # Prefer the most recent observation per market; use actual wholesale on ties.
    selected = {}
    for row in candidates:
        rank = (row["last_month"], row["observed_price_type"] == "Wholesale")
        old = selected.get(row["market"])
        if old is None or rank > (old["last_month"], old["observed_price_type"] == "Wholesale"):
            selected[row["market"]] = row
    now = today or date.today()
    output = []
    for row in selected.values():
        r = dict(row)
        year, month = map(int, r["last_month"].split("-"))
        age = max(0, (now.year - year) * 12 + now.month - month)
        r.update({"age_months": age, "stale": age > 6,
                  "price_status": "observed wholesale" if r["observed_price_type"] == "Wholesale"
                                  else "estimated wholesale from retail",
                  "grade_prices": grade_prices(r["market_price"]),
                  "grade_policy": POLICY_VERSION,
                  "forecast_is_past": bool(r.get("forecast_month") and r["forecast_month"] < now.strftime("%Y-%m")),
                  "grade_notice": "Indicative adjustments: A +4%, B base, C -5.5%. Not official UNBS price rules."})
        output.append(r)
    output.sort(key=lambda r: (not r["core_area"], -int(r["last_month"].replace("-", "")), r["market"]))
    return {"crop": crop, "crop_name": CROP_META[crop][0], "source": snapshot["source"],
            "generated_at": snapshot["generated_at"], "data_end": snapshot["data_end"],
            "rows": output}


def sms_preview(crop, market, grade="B", language="en", db=None):
    if grade not in {"A", "B", "C"}:
        raise ValueError("Choose grade A, B or C")
    row = prices(crop, market, db=db)["rows"][0]
    name = CROP_META[crop][1 if language == "sw" else 0]
    text = (f"FairPrice: {name}, {market}. {grade}: UGX {row['grade_prices'][grade]}/kg. "
            f"{'Mwezi' if language == 'sw' else 'Recorded'} {row['last_month']}. "
            f"{'Bei ya makadirio' if language == 'sw' else 'Indicative estimate'}. WFP/HDX.")
    return {"message": text, "status": "preview_only", "sent": False,
            "notice": "Preview only. No SMS provider is connected."}
