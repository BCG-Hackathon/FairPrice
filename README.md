# FairPrice

## Working local integration — 17 October 2026

Branch: `integration/original-ui-pricing`. See [integration and training audit](docs/INTEGRATION-AND-TRAINING.md).

**Updated farmer flow:** [flow, kiosk setup and remaining limits](docs/FARMER-FLOW.md). Language → crop → market → dated reference price. Calculations are expandable; the SMS simulator and model scores are in the footer's Kiosk staff view. Staff can configure the device's default market/language and 2/3/5-minute inactivity reset. The farmer SMS action explicitly reports unavailable service and collects no number. Crop quality is separate from price adjustment; verified A/B/C quality mappings remain unfinished.

This branch connects the team's saved ML pricing outputs to a working FastAPI backend and a kiosk recreated from the original green-and-white design. The remote frontend contained placeholders only. It does not use the separate polished design.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. API documentation: http://127.0.0.1:8000/docs.

For model verification, also install `ml/requirements.txt`, then run `python ml/verify_saved.py` with the same environment. Backend checks: install `backend/requirements-dev.txt`, then run `python -m pytest -c backend/pyproject.toml backend/tests`. UI DOM checks: `npm ci` followed by `npm run test:ui` against the running server.

Supported crops: **beans, maize grain, sorghum, millet, fresh cassava and leafy vegetables**. All prices show the market and observation month. A/B/C price multipliers are **1.04 / 1.00 / 0.945**, configured application estimates, not official UNBS premiums. The staff-only SMS simulator sends nothing; the farmer SMS action explains that real delivery is unavailable.

The kiosk provides English/Kiswahili navigation, crop search, market selection, realistic AI-generated crop images, dated observations, comparison and browser read-aloud where supported. Model scores are in the staff view, separate from the farmer's price. A service worker caches the small app shell and photos as used; opened crop responses are saved locally. Offline reload needs one successful online visit and service-worker installation. Unopened crops/photos and the staff simulator require connectivity. Browser speech languages depend on installed voices; Kiswahili and crop naming need local review.

The teammate's updated `feat/backend-scrape` branch (79bbdd4) is merged. Its SQLAlchemy/SQLite backend now loads the ML records with full source payloads. Default `DATA_MODE=published` uses `fairprice-published.db`, without synthetic prices or farmer registration. `/api/v1` catalog/status/prices and the kiosk endpoints share the same database and grade values. Synthetic reporting/offer/SMS/USSD demos remain available only with explicit `DATA_MODE=demo` and a separate database; they are not connected to the public kiosk flow.

There is no buyer/seller marketplace, live SMS gateway, live price collection, Azure deployment or image-grading model in this slice. Docker Compose is not supplied; use the commands above or `./run-local.ps1` after installing dependencies. The historical architecture below is an aspirational plan, not a delivery checklist.

---

Market price transparency for smallholder farmers in Northern Uganda: fair, verifiable prices for Category A and B produce, by kiosk tablet and by SMS/USSD on feature phones.

See [PLAN.md](PLAN.md) for the architecture and build plan.

## Layout

| Folder | What lives there |
|---|---|
| `backend/` | FastAPI app (API + serves the built React app), SMS/USSD state machine, pricing logic |
| `ml/` | Data ingestion (WFP/HDX), feature engineering, model training and backtest |
| `functions/` | Azure Functions timers: daily refresh, weekly brief, price alerts |
| `frontend/` | React + Tailwind kiosk PWA (offline-first) |
| `infra/` | Azure deploy script and SQL schema |
| `docs/` | Demo script and data sources |

## Quick start (local)

```bash
cp .env.example .env
docker compose up --build
```
