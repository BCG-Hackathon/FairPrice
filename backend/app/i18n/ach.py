"""Acholi (Luo) strings. Missing keys fall back to English.

DRAFT: these translations are a best effort and MUST be reviewed by a native
Acholi speaker before going live. Edit the strings here; no code changes needed.
"""

MESSAGES: dict[str, str] = {
    "main.menu": "FairPrice\n1. Nyige yen\n2. Dek ki Kodi\n3. Cam me cat\n4. Lok me cabit\n0. Lok leb",
    "market.prompt": "Yer cuk:",
    "lang.saved": "Leb ogwokke: Acholi. Cwal doki pi wel.",
    "error.invalid": "Yer pe tye atir. Tim ber item doki.",
    "prices.header": "{market} UGX/kg ki cabit mukato",
    "prices.line": "{crop} A:{a} B:{b} {trend}",
    "prices.updated": "Kiloko {date}",
    "prices.none": "Wel pe ma {market} kombedi.",
    "price.single": "{crop} {market} UGX/kg: A {a}, B {b}, {trend} ki cabit mukato. Kiloko {date}",
    "trend.up": "omedde {pct}%",
    "trend.down": "odok piny {pct}%",
    "trend.flat": "pe olokke",
    "trend.new": "manyen",
    "brief.header": "FairPrice cabit nio {date}:",
    "brief.up": "MALO: {items}",
    "brief.down": "PINY: {items}",
    "brief.item": "{crop} {market} {pct}%",
    "brief.none": "Wel pe olokke cabit-ni.",
    "brief.missing": "Lok me cabit pe kombedi.",
    "verdict.fair": "ATIR",
    "verdict.low": "TIDI",
    "verdict.very_low": "TIDI MATEK",
    "report.received": "Apwoyo. Ripot ogwokke: {crop} {grade} {price}/kg {market}.",
    "category.fruits": "Nyige yen",
    "category.vegetables_grains": "Dek ki Kodi",
    "category.cash_crops": "Cam me cat",
    "crop.avocado": "Avocado",
    "crop.banana": "Labolo",
    "crop.mango": "Muyembe",
    "crop.maize": "Anyuka",
    "crop.beans": "Muranga",
    "crop.tomato": "Nyanya",
    "crop.cassava": "Gwana",
    "crop.coffee": "Kawa",
}
