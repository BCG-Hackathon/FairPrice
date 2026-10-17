# FairPrice

## Working local integration — 17 October 2026

Branch: `integration/original-ui-pricing`. See [integration and training audit](docs/INTEGRATION-AND-TRAINING.md).

This branch connects the team's saved ML pricing outputs to a working FastAPI backend and a kiosk recreated from the original green-and-white design. The remote frontend contained placeholders only. It does not use the separate polished design.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. API documentation: http://127.0.0.1:8000/docs.

For model verification, also install `ml/requirements.txt`, then run `python ml/verify_saved.py` with the same environment. Checks: `python -m pytest backend/tests -q`.

Supported crops: **beans, maize grain, sorghum, millet, fresh cassava and leafy vegetables**. All prices show the market and observation month. A/B/C price multipliers are **1.04 / 1.00 / 0.945**, configured application estimates, not official UNBS premiums. The optional SMS panel is a preview and sends nothing.

The kiosk provides English/Kiswahili navigation, crop search, market selection, original crop illustrations, dated observations, historical forecasts, training information and browser read-aloud where supported. A service worker caches the app shell; opened crop responses are saved locally. Offline reload needs one successful online visit and service-worker installation. Unopened crops and SMS preview require connectivity. Browser speech languages depend on the installed voices; Kiswahili and crop naming need local review.

The historical plan below includes unimplemented features. There is no registry, buyer/seller marketplace, live SMS gateway, live price collection, Azure deployment, image-grading model or database integration in this local slice. Docker Compose is not supplied; use the commands above.

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
