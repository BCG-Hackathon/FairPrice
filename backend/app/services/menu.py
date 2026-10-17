"""Numbered menu shared by USSD and SMS.

`run_menu` is a pure function of (inputs so far, language at start) -> screen, so it is
trivial to test and works with Africa's Talking USSD (which resends the whole input
path, e.g. "2*1") as well as with our SMS menu (where we store the path per phone).

    [language picker, only until a language is saved]
    main: 1 Fruits / 2 Vegetables & Grains / 3 Cash crops / 4 Weekly brief / 0 Change language
      1-3 -> choose market -> END: prices for that category in that market
      4   -> END: weekly brief
      0   -> language picker -> END: saved
"""

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.config import Settings
from app.i18n import LANGUAGE_CHOICES, LANGUAGE_MENU, crop_name, format_short_date, format_ugx, t
from app.models import Category, Language, Market, PriceSnapshot
from app.services import catalog
from app.services.briefs import latest_brief, render_brief
from app.services.pricing import Trend, trend_of
from app.services.snapshot import list_snapshots

USSD_MAX_CHARS = 182
CATEGORY_CHOICES: dict[str, Category] = {
    "1": Category.FRUITS,
    "2": Category.VEGETABLES_GRAINS,
    "3": Category.CASH_CROPS,
}
BRIEF_CHOICE = "4"
LANGUAGE_CHOICE = "0"


@dataclass(frozen=True)
class MenuReply:
    text: str
    end: bool
    save_language: Language | None = None


class MenuData(Protocol):
    def markets(self) -> list[Market]: ...
    def prices_text(self, lang: Language, market: Market, category: Category) -> str: ...
    def brief_text(self, lang: Language) -> str: ...


def run_menu(inputs: list[str], language: Language | None, data: MenuData) -> MenuReply:
    steps = [s.strip() for s in inputs if s.strip() != ""]
    saved: Language | None = None

    if language is None:
        if not steps:
            return MenuReply(LANGUAGE_MENU, end=False)
        language = LANGUAGE_CHOICES.get(steps.pop(0))
        if language is None:
            return MenuReply(t(None, "error.invalid"), end=True)
        saved = language

    def reply(text: str, end: bool, save: Language | None = None) -> MenuReply:
        return MenuReply(text, end, save or saved)

    if not steps:
        return reply(t(language, "main.menu"), end=False)
    choice = steps.pop(0)

    if choice == LANGUAGE_CHOICE:
        if not steps:
            return reply(LANGUAGE_MENU, end=False)
        new_language = LANGUAGE_CHOICES.get(steps.pop(0))
        if new_language is None:
            return reply(t(language, "error.invalid"), end=True)
        return reply(t(new_language, "lang.saved"), end=True, save=new_language)

    if choice == BRIEF_CHOICE:
        return reply(data.brief_text(language), end=True)

    category = CATEGORY_CHOICES.get(choice)
    if category is None:
        return reply(t(language, "error.invalid"), end=True)

    markets = data.markets()
    if not steps:
        options = "\n".join(f"{i}. {m.name}" for i, m in enumerate(markets, start=1))
        return reply(f"{t(language, 'market.prompt')}\n{options}", end=False)
    index = steps.pop(0)
    if not index.isdigit() or not 1 <= int(index) <= len(markets):
        return reply(t(language, "error.invalid"), end=True)
    return reply(data.prices_text(language, markets[int(index) - 1], category), end=True)


def render_prices(
    lang: Language,
    market: Market,
    snapshots: list[PriceSnapshot],
    flat_band_pct: float,
    max_chars: int = USSD_MAX_CHARS,
) -> str:
    """e.g. 'Gulu UGX/kg vs last week / Maize A:1,250 B:900 up 5% / Updated 12 Oct'."""
    if not snapshots:
        return t(lang, "prices.none", market=market.name)
    header = t(lang, "prices.header", market=market.name)
    footer = t(lang, "prices.updated", date=format_short_date(max(s.as_of for s in snapshots)))
    lines = [header]
    for s in snapshots:
        line = t(
            lang,
            "prices.line",
            crop=crop_name(lang, s.crop.code),
            a=format_ugx(s.price_a),
            b=format_ugx(s.price_b),
            trend=trend_text(lang, s.change_pct, flat_band_pct),
        )
        if len("\n".join([*lines, line, footer])) > max_chars:
            break
        lines.append(line)
    return "\n".join([*lines, footer])


def trend_text(lang: Language, pct: float | None, flat_band_pct: float) -> str:
    trend = trend_of(pct, flat_band_pct)
    if trend in (Trend.UP, Trend.DOWN):
        return t(lang, f"trend.{trend.value}", pct=f"{abs(pct):.0f}")
    return t(lang, f"trend.{trend.value}")


class DbMenuData:
    """MenuData backed by the database."""

    def __init__(self, db: Session, settings: Settings, max_chars: int = USSD_MAX_CHARS) -> None:
        self._db = db
        self._settings = settings
        self._max_chars = max_chars

    def markets(self) -> list[Market]:
        return catalog.list_markets(self._db)

    def prices_text(self, lang: Language, market: Market, category: Category) -> str:
        snapshots = list_snapshots(self._db, market_code=market.code, category=category)
        return render_prices(lang, market, snapshots, self._settings.trend_flat_band_pct, self._max_chars)

    def brief_text(self, lang: Language) -> str:
        return render_brief(latest_brief(self._db), lang)
