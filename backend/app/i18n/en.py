"""English strings (default and fallback language).

SMS/USSD strings must stay plain GSM-7 text (no emoji, arrows or curly quotes)
so they render on every feature phone and fit the 160/182 character limits.
"""

MESSAGES: dict[str, str] = {
    # Menus
    "main.menu": "FairPrice\n1. Fruits\n2. Vegetables & Grains\n3. Cash crops\n4. Weekly brief\n0. Change language",
    "market.prompt": "Choose market:",
    "lang.saved": "Language saved: English. Dial again for prices.",
    "error.invalid": "Invalid choice. Please try again.",
    # Prices
    "prices.header": "{market} UGX/kg vs last week",
    "prices.line": "{crop} A:{a} B:{b} {trend}",
    "prices.updated": "Updated {date}",
    "prices.none": "No prices yet for {market}.",
    "price.single": "{crop} {market} UGX/kg: A {a}, B {b}, {trend} vs last week. Updated {date}",
    "trend.up": "up {pct}%",
    "trend.down": "down {pct}%",
    "trend.flat": "no change",
    "trend.new": "new",
    # Weekly brief
    "brief.header": "FairPrice week to {date}:",
    "brief.up": "UP: {items}",
    "brief.down": "DOWN: {items}",
    "brief.item": "{crop} {market} {pct}%",
    "brief.none": "Prices were stable this week.",
    "brief.missing": "No weekly brief yet.",
    "brief.subscribed": "You will get the weekly brief. Send BRIEF OFF to stop.",
    "brief.unsubscribed": "Weekly brief stopped. Send BRIEF ON to restart.",
    # Offer check
    "verdict.fair": "FAIR",
    "verdict.low": "LOW",
    "verdict.very_low": "VERY LOW",
    "offer.reply": "Offer {offer} for {crop} {grade} is {verdict}. Fair price about {floor}/kg ({market} sells {market_price}).",
    "offer.loss": " On {qty}kg you lose UGX {loss}.",
    # Field reports
    "report.received": "Thank you. Report saved: {crop} {grade} {price}/kg at {market}.",
    "report.review": " It will be checked before use.",
    # Help and errors
    "help": "FairPrice: send MENU for prices. Or PRICE MAIZE GULU, CHECK MAIZE 700, BRIEF, LANG",
    "error.crop": "Crop not found: {value}. Send HELP.",
    "error.market": "Market not found: {value}. Send HELP.",
    "error.format": "Wrong format. Example: {example}",
    # Categories
    "category.fruits": "Fruits",
    "category.vegetables_grains": "Vegetables & Grains",
    "category.cash_crops": "Cash crops",
    # Crops
    "crop.avocado": "Avocado",
    "crop.banana": "Banana",
    "crop.mango": "Mango",
    "crop.maize": "Maize",
    "crop.beans": "Beans",
    "crop.tomato": "Tomato",
    "crop.cassava": "Cassava",
    "crop.coffee": "Coffee",
}
