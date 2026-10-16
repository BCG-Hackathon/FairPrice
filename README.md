# FairPrice

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
