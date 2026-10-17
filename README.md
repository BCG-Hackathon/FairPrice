# FairPrice

Market price transparency for smallholder farmers in Northern Uganda: fair, verifiable prices for Category A and B produce, via kiosk tablet and SMS/USSD on feature phones.

See [PLAN.md](PLAN.md) for the architecture and build plan.

## Layout

| Folder | What lives there |
|---|---|
| `backend/` | FastAPI app: prices, Offer Check, field reports, weekly brief, SMS/USSD channels |
| `ml/` | Data ingestion (WFP/HDX), feature engineering, model training and backtest |
| `functions/` | Azure Functions timers: daily refresh, weekly brief, price alerts |
| `frontend/` | React + Tailwind kiosk PWA (offline-first) |
| `infra/` | Azure deploy script and SQL schema |
| `docs/` | Demo script and data sources |

## Backend quick start (Windows, Git Bash)

```bash
cd backend
py -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest                       # run tests
.venv/Scripts/python -m uvicorn app.main:app --reload # http://localhost:8000/docs
```

On macOS/Linux use `python3 -m venv .venv` and `.venv/bin/python`.
Copy `.env.example` to `.env` to change settings. By default it uses a local SQLite file seeded with demo data.

### Try the channels

```bash
# USSD (Africa's Talking format). text is the path of choices, e.g. "1*2*1"
curl -X POST localhost:8000/api/v1/channels/ussd -d sessionId=s1 -d phoneNumber=%2B256711111111 -d text=

# SMS keywords
curl -X POST localhost:8000/api/v1/channels/sms -d from=%2B256711111111 --data-urlencode "text=CHECK MAIZE 300 200 GULU"
```
