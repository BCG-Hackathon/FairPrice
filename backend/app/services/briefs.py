"""Weekly Market Brief: biggest risers and fallers, rendered from hardcoded templates."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.i18n import crop_name, format_short_date, t
from app.models import Language, MarketBrief, utcnow
from app.services.snapshot import list_snapshots

TOP_N = 3
SMS_MAX_CHARS = 306  # two concatenated SMS segments


def generate_brief(db: Session, settings: Settings) -> MarketBrief | None:
    """Snapshot the week's movers into a stored brief. Returns None if there are no prices."""
    snapshots = [s for s in list_snapshots(db) if s.change_pct is not None]
    if not snapshots:
        return None
    movers = [
        {
            "crop_code": s.crop.code,
            "market_code": s.market.code,
            "market_name": s.market.name,
            "price_a": s.price_a,
            "change_pct": s.change_pct,
        }
        for s in snapshots
        if abs(s.change_pct) >= settings.trend_flat_band_pct
    ]
    risers = sorted((m for m in movers if m["change_pct"] > 0), key=lambda m: -m["change_pct"])[:TOP_N]
    fallers = sorted((m for m in movers if m["change_pct"] < 0), key=lambda m: m["change_pct"])[:TOP_N]

    brief = MarketBrief(
        period_end=max(s.as_of for s in snapshots),
        items=[{**m, "direction": "up"} for m in risers] + [{**m, "direction": "down"} for m in fallers],
        generated_at=utcnow(),
    )
    db.add(brief)
    db.commit()
    db.refresh(brief)
    return brief


def latest_brief(db: Session) -> MarketBrief | None:
    return db.scalar(select(MarketBrief).order_by(MarketBrief.generated_at.desc()).limit(1))


def render_brief(brief: MarketBrief | None, lang: Language | None) -> str:
    """Plain GSM-7 text, short enough for SMS."""
    if brief is None:
        return t(lang, "brief.missing")
    lines = [t(lang, "brief.header", date=format_short_date(brief.period_end))]
    for direction in ("up", "down"):
        items = [i for i in brief.items if i["direction"] == direction]
        if items:
            rendered = ", ".join(
                t(
                    lang,
                    "brief.item",
                    crop=crop_name(lang, i["crop_code"]),
                    market=i["market_name"],
                    pct=f"{i['change_pct']:+.0f}",
                )
                for i in items
            )
            lines.append(t(lang, f"brief.{direction}", items=rendered))
    if len(lines) == 1:
        lines.append(t(lang, "brief.none"))
    return "\n".join(lines)[:SMS_MAX_CHARS]
