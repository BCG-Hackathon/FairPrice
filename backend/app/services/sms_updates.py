"""SMS price updates built from the local database (the same records the kiosk shows).

* Farmers: a simple list per category (vegetables, fruits, grains/crops): each crop's price
  per kg for grades A/B/C (average across markets with recent records) and a one-word trend
  from the ML team's forecasts.
* Buyers/suppliers: for each reviewed buyer with a published phone, where their crop is
  currently traded (recent WFP market records), at their grade's price, plus the model trend.

Prices are never generated here: they come from published.prices() (WFP/HDX records and the
saved model forecasts). Text is plain GSM-7; buyer texts stay within 2 SMS parts (306
characters), the farmer list within 4 (612) so every crop and price is spelled out.
"""

from datetime import date
from statistics import mean

from app.services.grade_policy import grade_prices
from app.services.published import CROP_META, prices

SMS_MAX_CHARS = 306
SMS_FARMER_MAX_CHARS = 612
STEADY_BAND = 0.02  # model change within +/-2% reads as "steady"
MONTHS = {
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    "sw": ("Jan", "Feb", "Mac", "Apr", "Mei", "Jun", "Jul", "Ago", "Sep", "Okt", "Nov", "Des"),
}
CATEGORY_LABEL = {
    "en": {"vegetables": "VEGETABLES", "fruits": "FRUITS", "grains": "GRAINS/CROPS"},
    "sw": {"vegetables": "MBOGA", "fruits": "MATUNDA", "grains": "NAFAKA"},
}
TEXT = {
    "en": {
        "farmer_title": ("FairPrice market prices\nPrice for 1 kg in Uganda shillings (UGX)\n"
                         "Grade A = best, B = good, C = lower quality"),
        "none": "No changes",
        "trend": {"up": "rising", "down": "falling", "steady": "steady"},
        "farmer_footer": "Market prices from {month}. Guide only, not an offer.",
        "buyer_title": "FairPrice for {name}: {crop} grade {grade}, UGX/kg",
        "traded": "Recently traded: {places}",
        "buyer_model": "Model trend {month}: {pct}",
        "buyer_footer": "Farmers via kiosk staff. Guide prices, not offers.",
        "stale_note": "* older than 6 months. ",
    },
    "sw": {
        "farmer_title": ("FairPrice bei za soko\nBei ya kilo 1 kwa shilingi za Uganda (UGX)\n"
                         "Daraja A = bora, B = nzuri, C = ubora wa chini"),
        "none": "Hakuna mabadiliko",
        "trend": {"up": "inapanda", "down": "inashuka", "steady": "imetulia"},
        "farmer_footer": "Bei za soko za {month}. Mwongozo tu, si ofa.",
        "buyer_title": "FairPrice kwa {name}: {crop} daraja {grade}, UGX/kg",
        "traded": "Inauzwa hivi karibuni: {places}",
        "buyer_model": "Mwenendo wa modeli {month}: {pct}",
        "buyer_footer": "Wakulima kupitia kioski. Bei za mwongozo, si ofa.",
        "stale_note": "* zaidi ya miezi 6. ",
    },
}


def _month(value: str | None, language: str = "en") -> str:
    """'2026-08' -> 'Aug 2026'."""
    if not value:
        return "-"
    year, month = value.split("-")[:2]
    return f"{MONTHS[language][int(month) - 1]} {year}"


def _ugx(amount: float) -> str:
    return f"{round(amount):,}"


def _pct(change: float) -> str:
    return f"{change * 100:+.0f}%"


def crop_summary(db, crop: str, today: date | None = None) -> dict | None:
    """Average price over markets with recent (not stale) records, and the model's estimate."""
    try:
        rows = prices(crop, db=db, today=today)["rows"]
    except KeyError:
        return None
    recent = [r for r in rows if not r["stale"]] or rows  # fall back to older records, flagged
    base = mean(r["market_price"] for r in recent)
    with_model = [r for r in recent if r.get("market_price_forecast") is not None]
    model = None
    if with_model:
        now = mean(r["market_price"] for r in with_model)
        estimate = mean(r["market_price_forecast"] for r in with_model)
        model = {
            "price": round(estimate),
            "change": estimate / now - 1,
            "month": max(r["forecast_month"] for r in with_model),
            "is_past": any(r.get("forecast_is_past") for r in with_model),
        }
    return {
        "crop": crop,
        "base_price": round(base),
        "grades": grade_prices(round(base)),
        "markets": len(recent),
        "recorded": max(r["last_month"] for r in recent),
        "stale": all(r["stale"] for r in recent),
        "model": model,
    }


def farmer_update(db, categories: list[str], language: str = "en", today: date | None = None) -> dict:
    """Card + SMS text for farmers: one line per crop with A/B/C prices per kg and a trend word."""
    text = TEXT[language]
    sections = []
    for category in categories:
        items = [
            summary
            for crop, meta in CROP_META.items()
            if meta[2] == category and (summary := crop_summary(db, crop, today))
        ]
        sections.append({"category": category, "items": items})

    lines = [text["farmer_title"]]
    for section in sections:
        label = CATEGORY_LABEL[language][section["category"]]
        if not section["items"]:
            lines.append(f"\n{label}: {text['none']}")
            continue
        lines.append(f"\n{label}")
        for item in section["items"]:
            name = CROP_META[item["crop"]][1 if language == "sw" else 0]
            grades = item["grades"]
            line = ", ".join(f"{grade} UGX {_ugx(grades[grade])}" for grade in "ABC")
            line = f"{name}: {line}"
            if item["model"]:
                change = item["model"]["change"]
                direction = "steady" if abs(change) < STEADY_BAND else "up" if change > 0 else "down"
                line += f" ({text['trend'][direction]})"
            lines.append(line)
    recorded = max((i["recorded"] for s in sections for i in s["items"]), default=None)
    footer = "\n" + text["farmer_footer"].format(month=_month(recorded, language))
    return {"sections": sections, "recorded": recorded, "sms": _fit(lines, footer, SMS_FARMER_MAX_CHARS)}


def buyer_update(db, listing, language: str = "en", today: date | None = None) -> dict:
    """Card + SMS text for one reviewed buyer: where their crop/grade trades now, and the trend."""
    text = TEXT[language]
    rows = prices(listing.crop, db=db, today=today)["rows"]
    # Up to three markets: recent records first, newest first.
    rows = sorted(rows, key=lambda r: (r["stale"], -int(r["last_month"].replace("-", ""))))[:3]
    places = [
        f"{r['market'].split('(')[0].strip()} {_ugx(r['grade_prices'][listing.grade])} "
        f"{_month(r['last_month'], language)}{'*' if r['stale'] else ''}"
        for r in rows
    ]
    summary = crop_summary(db, listing.crop, today)
    crop_name = CROP_META[listing.crop][1 if language == "sw" else 0]
    lines = [
        text["buyer_title"].format(name=listing.name[:30], crop=crop_name, grade=listing.grade),
        text["traded"].format(places="; ".join(places)),
    ]
    if summary and summary["model"]:
        lines.append(text["buyer_model"].format(
            month=_month(summary["model"]["month"], language), pct=_pct(summary["model"]["change"])))
    return {
        "buyer_id": listing.id,
        "crop": listing.crop,
        "grade": listing.grade,
        "markets": [{"market": r["market"], "price": r["grade_prices"][listing.grade],
                     "recorded": r["last_month"], "stale": r["stale"]} for r in rows],
        "model": summary["model"] if summary else None,
        "sms": _fit(lines, (text["stale_note"] if any(r["stale"] for r in rows) else "") + text["buyer_footer"]),
    }


def _fit(lines: list[str], footer: str, limit: int = SMS_MAX_CHARS) -> str:
    """Keep the footer (date/source) and trim the body if the SMS would exceed the limit."""
    body = "\n".join(lines)
    room = limit - len(footer) - 1
    if len(body) > room:
        body = body[: room - 3].rstrip() + "..."
    return f"{body}\n{footer}"
