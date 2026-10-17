# Farmer flow and kiosk setup

Implemented 17 October 2026. This supersedes earlier descriptions of SMS and training buttons in the main header.

## Farmer journey

Language → crop category → crop → market → dated reference price.

The result leads with the crop, market, recorded month and base UGX/kg amount. It states whether this is published wholesale or a wholesale estimate derived from retail. A/B/C calculations are in an expandable section and retain the requested +4%, base, −5.5% rules. Repeated crop photos were removed from the grade cards because they conveyed no quality difference. No farmer account, weighing or buyer/seller listing is required.

Quality guidance is separate from price adjustment. The app does not inspect produce or certify quality. The bean view links the public UNBS dry-bean guide and explains that its grades 1/2/3 are not mapped to the app's A/B/C labels. Other crop views explicitly say verified guidance is not yet available. No invented official grade photos or thresholds are displayed.

UNBS source reviewed: https://webstore.unbs.go.ug/standards/DRY_BEANS_-_BEST_PRACTICES_FOR_IMPROVED_NUTRITION_AND_INCOMES.pdf. Its guidance covers foreign matter, damaged/broken beans and measured moisture, among other requirements. Full crop-specific mappings and local review remain necessary.

## Dates and comparison

All records remain dated references, not real-time offers. Over-six-month-old records display “No recent price available” and label the amount as an older reference. Six months is the existing demo freshness policy, not an official guarantee of usability; individual programmes may need stricter thresholds.

Comparison uses the selected crop only, UGX/kg, at wholesale level. It lists each record's date and distinguishes observed wholesale from estimates. Different-month comparisons are explicitly flagged; assumed conversions are marked. There is no “best profit” ranking or transport-cost invention. Monthly records carry a month, not a claimed exact observation day.

Successful public records are cached with their save time. A network/service failure may use the saved record with an offline/service notice. A 4xx response (for example, a removed crop) clears that cached response instead of resurrecting it. Cached dates are never rewritten to today. The app shell needs an initial online visit and successful service-worker installation before offline reload.

Only the small HTML/CSS/JavaScript shell is precached on installation. Crop photos are cached as they are used and reused locally, avoiding an automatic download of every full-resolution photo at kiosk setup. Unopened photos may be unavailable offline. The current source PNGs still need dedicated compression for a bandwidth-constrained rollout.

## Taking away a result

Read aloud uses the displayed crop, market, base amount and recorded date; old references are announced. Kiswahili speech is blocked with an understandable message if a Kiswahili voice is unavailable, rather than reading it with an unrelated voice.

“Send this price by SMS” currently opens an explicit unavailable notice. It collects no phone number, creates no queue and claims neither submission nor delivery. Users without phones can read, listen or write down the information. A real provider integration, provisioning and delivery-state handling remain unfinished.

## Staff view

The footer's Kiosk staff entry contains:

- Device-local kiosk name, preferred market, starting language and inactivity timeout (2/3/5 minutes).
- Source coverage date and service limitations.
- A clearly labelled SMS simulator and model/data information.

The configured market is selected only if that crop has a record there. Otherwise, the market step selects an available core-area market, then shows its recorded date for user confirmation. The preference is not a claim about the physical kiosk's GPS position.

Settings are stored on the device. This is a public setup view, not an authenticated administration portal. It contains no provider keys, farmer records or privileged backend mutation controls. Keep sensitive administration separate when those functions are introduced.

## Shared-device reset

After inactivity, a 15-second warning offers continued use. At the configured timeout, the app returns to the starting language screen, clears current crop/market/search/modal state and stops speech. In-flight navigation cannot reopen the old crop after reset. Device settings and public price caches are retained; they contain no phone numbers.

## Verification

DOM integration checks exercise all six crop-market-price journeys, calculation values, collapsed technical detail, comparison, old-record warnings, unavailable SMS without number collection, staff simulator/training, saved-record fallback, cache invalidation on 404, default-market setup and inactivity warning/reset. Backend tests cover truthful capability flags alongside existing pricing and database parity checks.

Real device acceptance still needs language review, screen/speech checks, actual offline reload and any future handset SMS integration. Fresh published data ingestion and crop-specific quality mappings are not supplied by this UI update.
