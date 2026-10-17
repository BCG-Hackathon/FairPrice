"""Hardcoded translations. Only numbers, trends and dates are dynamic."""

from datetime import date

from app.i18n import ach, en, sw
from app.models import Language

CATALOGS: dict[Language, dict[str, str]] = {
    Language.EN: en.MESSAGES,
    Language.SW: sw.MESSAGES,
    Language.ACH: ach.MESSAGES,
}

# Language picker is the same in every language (shown before we know the user's choice).
LANGUAGE_MENU = "FairPrice\n1. English\n2. Kiswahili\n3. Acholi"
LANGUAGE_CHOICES: dict[str, Language] = {"1": Language.EN, "2": Language.SW, "3": Language.ACH}

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def t(lang: Language | None, key: str, **kwargs: object) -> str:
    """Translate `key`, falling back to English, then to the key itself."""
    catalog = CATALOGS.get(lang or Language.EN, en.MESSAGES)
    template = catalog.get(key) or en.MESSAGES.get(key) or key
    return template.format(**kwargs) if kwargs else template


def crop_name(lang: Language | None, code: str) -> str:
    return t(lang, f"crop.{code}")


def format_ugx(amount: float) -> str:
    return f"{round(amount):,}"


def format_short_date(d: date) -> str:
    """'12 Oct': language-neutral and GSM-7 safe."""
    return f"{d.day} {_MONTHS[d.month - 1]}"
