# FairPrice: what is connected, what the model learned, and what remains

17 October 2026. Current implementation takes priority over aspirational PLAN.md.

## Branch evidence

The inspected remote branches were:

| Branch | Commit | Actual contents |
|---|---|---|
| main | c3d41cb | Architecture plan and placeholder folders/files |
| feat/backend-scrape | c3d41cb | Same commit as main; no additional backend implementation |
| ml-pricing | ad5cb89 | Ingestion, features, LightGBM training, saved model, processed observations, snapshots and metrics |
| integration/original-ui-pricing | integration work | Starts at ml-pricing; adds the API, kiosk, crop illustrations, SMS preview and checks |

Original remote branch work is preserved. The original Canva layout was recreated in code because the frontend branch had no implemented UI. Green header, language choice, simple categories, crop list and A/B/C cards remain. Unsupported mango/fruit prices were removed. The separate fair-value-polished design is not imported. The frontend is deliberately plain HTML/CSS/JavaScript served by FastAPI; the planned React toolchain did not yet exist.

## The data actually used

WFP Uganda monthly prices, filtered by the team's ingestion code to Northern Uganda, UGX/kg and six products. The committed processed file has 5,925 records and no duplicate crop/market/price-type/month keys in the checked data.

| Crop | Observations | Markets | First month | Last month | Model holdout MAPE | Last-price baseline MAPE |
|---|---:|---:|---|---|---:|---:|
| Beans | 1,550 | 19 | 2008-06 | 2026-08 | 8.73% | 9.05% |
| Maize | 1,563 | 19 | 2006-01 | 2026-08 | 14.24% | 15.31% |
| Sorghum | 1,332 | 19 | 2011-04 | 2026-08 | 14.19% | 15.18% |
| Millet | 586 | 11 | 2011-04 | 2026-01 | 9.68% | 10.09% |
| Fresh cassava | 448 | 7 | 2020-12 | 2026-08 | 28.12% | 32.36% |
| Leafy vegetables | 446 | 7 | 2020-12 | 2026-08 | 30.77% | 36.07% |

Not every crop exists in Gulu or Lira. The selector uses actual markets available per crop. Leafy vegetables are a source category, not evidence for spinach/okra/any particular species. Fresh cassava is not cassava flour. Six original SVG illustrations distinguish these crops without claiming photo-based grading or official quality certification.

Source: https://data.humdata.org/dataset/wfp-food-prices-for-uganda. The raw downloaded CSV was not committed, so its provenance and cleaning cannot yet be independently re-created from the original download. Snapshot dates are preserved, not changed to the launch date.

## How training works, simply

The model looks at a crop's current recorded price, previous changes, moving averages, volatility, the time of year and its crop/market/region/price-type categories. It learns the change to the following month:

`target = log(next month's price) − log(this month's price)`

`forecast = this month's price × exp(predicted change)`

There are 5,585 labelled adjacent month-pairs. The team's training reserves the last 12 forecast-origin months, from August 2025, for 626 predictions and trains initially on 4,959 pairs. The final saved model then trains on all labelled pairs. LightGBM uses 400 trees, learning rate 0.03, 15 leaves, L1 objective and seed 42. A crop only uses the model when its holdout MAPE beats the last-price baseline; all six currently do on that criterion.

The integration reran the held-out evaluation and loaded the team's saved final model. **Overall and per-crop metrics reproduced exactly, and every saved final-model forecast matched the snapshot.** See `docs/model-verification.json` for hashes and results. The original model and metrics were not overwritten.

Overall MAPE is 16.71% versus baseline 18.53%. This is not a claim of 83.29% accuracy. Only 47.1% of model predictions were within 10% of the actual value, versus 48.7% for the baseline: the model improves average percentage error, not every metric. Cassava and leafy vegetables have particularly high errors. These are development results, not validated financial advice or measured income impact.

## What the displayed amount means

1. WFP observed retail/wholesale price remains visible, with its market and month.
2. For retail records, the team's pipeline estimates wholesale-level prices using a factor. Beans: 0.842; maize: 0.883, based on historical paired Lira data. Sorghum, millet, fresh cassava and leafy vegetables: assumed 0.875, pooled from beans/maize. These assumed conversions are not locally measured wholesale prices. Wholesale source records use factor 1.
3. The backend applies the requested indicative grade adjustments to this base: A ×1.04; B ×1.00; C ×0.945. It rounds once to whole UGX using decimal half-up rounding, shared by kiosk and SMS. It does not apply another grade adjustment to an already adjusted snapshot.
4. WFP records are not labelled with these A/B/C grades. Accordingly, the cards are pricing scenarios, not observed grade-specific offers. UNBS/East African quality standards do not establish our premiums on the evidence reviewed. Crop-specific standards and a verified quality mapping are still needed before certification claims.

The app does not call this a guaranteed farmgate price or deduct invented transport/trader margins. It displays one actual market record at a time rather than a regional median mixing observation months. When both retail and wholesale exist, it chooses the latest observation for that market and actual wholesale on a date tie.

The latest dataset month is August 2026; the forecast for a series is one month after its own latest observation. In October 2026, these are **historical forecasts**, not forecasts for next month from today. Millet's latest record is January 2026; some Gulu records end in April and Lira records in December 2025. Staleness is recomputed against the calendar, not just against the dataset's end date.

UNBS reference checked: https://webstore.unbs.go.ug/store.php?src=3079 (US EAS 329:2017, Fresh mango — Specification; its public abstract describes requirements, sampling and test methods, not our percentages). This mango reference does not substitute for standards for the six supported crops.

## Runtime and user journey

`Browser kiosk → /api/crops → supported crop → /api/prices/{crop} → market record → shared grade calculation`

The app uses saved ML outputs for fast deterministic service. It does not load an uploaded pickle or call an LLM on user requests. The saved LightGBM model is verified offline with `ml/verify_saved.py`. This avoids presenting static snapshots as live model inference.

No registration: choose English/Kiswahili, choose category, search/select crop, select market, see dated values, optionally read aloud or open SMS preview. Back buttons return to crop/category/language; header returns home. SMS preview can independently choose crop, market and grade and calls the same pricing service. No phone number is collected and no message is sent.

The backend mounts the frontend and assets on the same host. A service worker caches public app files, and the frontend stores successfully retrieved public records with cache timestamps. Offline use is limited to records already opened, after the initial online setup. The cache timestamp never replaces the observation month. SMS preview requires the backend. Browser speech depends on device voices, and no Acholi language support is claimed.

## Checks and launch

Use README's PowerShell commands. The API starts at http://127.0.0.1:8000; docs at `/docs`. Tests check the six crops/assets, all returned markets, valid positive amounts, decimal rounding, calendar staleness, kiosk/SMS equality, missing crop/market and invalid grades. JavaScript syntax checks cover the kiosk and service worker. `ml/verify_saved.py` verifies saved-model forecasts and reproduces evaluation without replacing team artifacts.

Backend/API and model verification were executed locally. Browser layout, speech, real handset SMS and service-worker offline reload require device/browser acceptance; file/API checks alone do not prove them. No Azure deployment or paid services were started.

## Next work, in priority order

1. **Data analyst:** provide the raw source CSV, retrieval date and source hash. Review `ingest_wfp.py`: its centred seven-record outlier median uses future records, so use a causal trailing/reference-only cleaning rule and evaluate sensitivity. Preserve/flag suspicious observations rather than silently discarding genuine shocks. Re-ingest and retrain before strengthening accuracy claims.
2. **ML analyst:** reserve an untouched final time window after model/baseline selection, run rolling-origin evaluation and report errors per market/crop plus prediction intervals. Fit any retail-to-wholesale conversion only on the applicable historical training window. The current retail forecast scores do not validate wholesale conversion errors or grade premiums. Same-month cross-market features also assume all monthly reports are available at inference time; enforce publication lags for live forecasting.
3. **Backend developer:** automate permitted source refreshes, validate records before replacing the public snapshot, retain versions, and only publish forecasts whose origin/horizon match the intended use. A database and Azure refresh deployment are next steps, not already functioning services. Keep credentials server-side.
4. **UX/field reviewer:** check local language and crop terminology, official crop-specific quality criteria, photos if needed, tablet readability, touch targets, speech availability and offline reload. Validate that users understand estimated wholesale versus an actual buyer offer.
5. **SMS developer:** provision a Uganda-capable provider/sender ID, handle consent for requested messages, rate limits, costs and multipart length, and persist provider delivery states. A preview is not a real handset test. No unsolicited broadcast is included.
6. **Demo lead:** show beans or maize first, disclose the recorded month and conversion, compare A/B/C, then show the basic-phone preview. Explain that transparency can improve negotiation; do not claim that this prototype has already raised incomes or ended hunger.
