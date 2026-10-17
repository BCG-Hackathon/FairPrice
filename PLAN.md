# FairPrice: Build Plan

> The working plan. We build one step at a time and tick progress here.
>
> **Progress:** ✅ 0 Skeleton · ✅ 1 Backend MVP (38 tests passing) · ⬜ 2 Azure deploy · ⬜ 3 Scheduled refresh (Functions) · ⬜ 4 Azure OpenAI · ⬜ 5 Polish + demo

## Context
Clara Commune runs 30 village groups in Northern Uganda. Her farmers sell produce for about ⅓ of what it fetches in Gulu, Lira or Kenya, because brokers control the price information. **FairPrice is the source of truth on prices.** It shows the real market price for Category A and Category B produce, how it changed since last week, and when it was last updated. A farmer walks into a negotiation knowing what the produce is worth.

There are two kinds of users and two channels:
- **Farmers with feature phones** use **USSD** (numbered menu) or **SMS** (menu or keywords).
- **Kiosk attendants** use the solar **tablet** at the village hub. They inform farmers who have no phone.

Rules we keep:
1. **Prices are deterministic.** They come from data in SQL, plus the model team's forecasts. No LLM ever invents a price.
2. **Every language string is hardcoded** (English default, Kiswahili, Acholi). Only numbers, trends and dates are dynamic, e.g. "Maize A: 1,250 up 5% vs last week · Updated 12 Oct".
3. **Every price shows its last-updated date and its data source.**

## Feasibility review (15h budget)
The first plan had too much in it to finish: ML, LLM, Maps, QR, Functions and Azure all at once. The revised scope:

| Item | Decision | Why |
|---|---|---|
| Backend API, SMS/USSD, briefs, reports | **MVP: build now** | This is the product. Other teams build on top of it. |
| Seed data (realistic, labeled `seed`) | **MVP** | Unblocks the frontend team now. The model/data team replaces it through the import endpoints. |
| Transport cost | **MVP, simple** | Straight-line distance × road factor × UGX/kg/km. Azure Maps can replace it later through the same interface. |
| Azure Container Apps + Azure SQL | Step 2 | Code already runs on both SQLite and Azure SQL (SQLAlchemy). |
| Azure Functions timer | Step 3 | Calls `POST /api/v1/admin/refresh` and `/admin/briefs/generate`. Tiny. |
| Azure OpenAI | Step 4, one feature | An English kiosk-staff brief narrative, built from validated numbers. Optional: extract prices from Clara's unstructured messages. |
| Azure Maps routing, QR ticket | Stretch | Only if time allows. |
| **Collective selling (group bulk sale)** | **⏰ REMINDER: revisit after MVP** | The biggest impact lever, but not needed for the MVP. |

**MVP by midnight:** all endpoints below work locally with seed data, the tests pass, and the frontend team can build against `/docs`.

## Feature: Offer Check (previously "Negotiation Coach")
A farmer gets an offer from a broker, e.g. "700 UGX/kg for my maize". They (or the kiosk attendant) send `CHECK MAIZE 700` by SMS, or use the tablet. FairPrice compares the offer to the **fair farm-gate price**:

`fair farm-gate price/kg = market price × (1 − trader margin 20%) − transport cost/kg to that market`

The reply comes in three bands: **FAIR** (≥ fair price), **LOW** (≥ 85% of it) or **VERY LOW**. It also shows what the farmer stands to lose:
`"Offer 700 is LOW. Fair price ~980/kg (Gulu sells 1,250). On 200kg you lose UGX 56,000."`
This is the ground-truth price applied to the one moment that matters, the negotiation. It's deterministic and needs no LLM.

## Weekly Market Brief
Generated from the snapshot data: the biggest risers and fallers, with % change. Stored in structured form and **rendered in each language from hardcoded templates**.
- Kiosk staff see it on the tablet (`GET /briefs/latest`).
- Farmers get it by SMS (`BRIEF` on request, or a weekly broadcast to subscribers; `BRIEF OFF` to stop). Plain GSM-7 text only, so it works on any feature phone.

## Keeping data live across connectivity tiers
Assumptions about what Clara has: a smartphone with mobile data and a laptop at the district office in Gulu town (good 3G/4G). Each kiosk has a solar Android tablet with patchy data. Group leaders have 2G feature phones.

| Tier | Who / device | How data gets in |
|---|---|---|
| Cloud (no field connectivity needed) | Automated | Azure Functions pulls WFP/HDX, KAMIS etc. → `POST /admin/prices/import`. Village connectivity doesn't matter. |
| Good connectivity | Clara / BCG / devs on a laptop | Upload a CSV of official bulletins (`/admin/prices/import`), review flagged reports. Later: an LLM extracts prices from forwarded WhatsApp text. |
| Intermittent | Kiosk tablet | Attendant records prices seen at the hub. They're **queued offline with a `client_ref`** and synced in a batch when signal returns (`POST /reports`; idempotent, so retries never duplicate). |
| 2G only | Group leader's feature phone | `REPORT MAIZE A 1200 GULU` by SMS. The network stores and forwards it. |

Field reports are auto-checked against the current price. If one deviates more than 35%, it's **flagged** for review. Reports from unregistered numbers are **pending**. Accepted reports feed the next refresh.

## Backend design (Step 1)
- **Stack:** FastAPI · SQLAlchemy 2.0 · Pydantic v2 + pydantic-settings · pytest. Virtual env at `backend/.venv`, dependencies in `backend/requirements.txt` (plus `requirements-dev.txt` and `requirements-azure.txt` for the pyodbc driver).
- **App factory** (`create_app(settings)`): the engine and session factory live on `app.state`, so tests use an isolated in-memory DB.
- **Azure SQL-safe models:** every string has a length, Unicode text is NVARCHAR, enums are stored as strings, no NULL unique columns, and timestamps are UTC.
- **Low-bandwidth:** gzip, plus `ETag` / `304 Not Modified` on the snapshot so the kiosk only downloads when data changed.
- **Channel adapters:** the USSD/SMS payloads match Africa's Talking. The `SmsGateway` interface has a console/outbox implementation now (powers the in-app phone simulator) and Africa's Talking later.
- **One menu engine** drives both USSD and SMS menus. Language is chosen once per phone and stored; `0` changes it.

```
backend/
  requirements.txt  requirements-dev.txt  requirements-azure.txt  pyproject.toml (pytest/ruff config)
  app/
    main.py            create_app, lifespan (create tables + seed), routers
    config.py          Settings (env / .env)
    db.py              Base, engine/session factory, get_db
    models.py          ORM tables
    schemas.py         Pydantic request/response models
    deps.py            DB session, settings, transport, SMS gateway, admin-token dependencies
    api/               status · catalog · prices · offers · reports · briefs · channels · admin
    services/          pricing (pure rules) · transport · snapshot · offers · reports · briefs
                       menu (USSD+SMS engine) · channels (USSD/SMS handlers) · sms_gateway · importers · catalog
    i18n/              en.py · sw.py · ach.py (hardcoded strings) + t()
    content/           grade_standards.json (A vs B descriptions, image paths)
    seed/              markets.json · kiosks.json · crops.json · seed.py
  tests/
```

### Endpoints (`/api/v1`, OpenAPI at `/docs`)
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/status` | Last updated, data sources and freshness, counts |
| GET | `/crops`, `/markets`, `/kiosks` | Catalog |
| GET | `/crops/{code}/grades` | Category A vs B standards (descriptions + images) |
| GET | `/prices/snapshot?market=&category=&kiosk=` | Ticker: A/B price, % change vs last week, trend, forecast, updated date; fair farm-gate floor if `kiosk` given. ETag. |
| GET | `/prices/history?crop=&market=&weeks=` | Graph series + forecast points |
| GET | `/prices/compare?crop=&grade=&kiosk=&quantity_kg=` | Markets ranked by net after transport |
| POST | `/offers/check` | Offer Check verdict |
| POST | `/reports` | Field price reports (batch, idempotent) |
| GET | `/briefs/latest?lang=` | Weekly brief (structured + rendered text) |
| POST | `/channels/ussd` | Africa's Talking USSD callback (`CON`/`END`) |
| POST | `/channels/sms` | Inbound SMS (menu + keywords). Returns the reply and queues it in the outbox. |
| GET | `/channels/sms/outbox?phone=` | Phone simulator / audit |
| POST | `/admin/refresh` | Recompute snapshots (called by Azure Functions) |
| POST | `/admin/briefs/generate`, `/admin/briefs/broadcast` | Weekly brief job + SMS broadcast |
| POST | `/admin/prices/import`, `/admin/forecasts/import` | CSV ingestion (data + model team contract) |
| GET/PATCH | `/admin/reports` | Review flagged/pending reports |
Admin routes require the `X-Admin-Token` header.

### Contracts for the other teams
- **Model team:** CSV `market_code,crop_code,period_start,predicted_ugx_per_kg,lower,upper,model_version` → `/admin/forecasts/import`. Until it arrives, the snapshot uses a naive trend forecast (`forecast_source: "naive"`).
- **Data team:** CSV `market_code,crop_code,observed_on,price,currency,unit_kg,source` → `/admin/prices/import` (KES converted to UGX automatically).
- **Frontend:** `/docs`. The snapshot and history endpoints drive the ticker and graphs. `generated_at` drives the "Last updated" label.

## Verification
- `cd backend && .venv/Scripts/python -m pytest` covers pricing math, menu flow (language saved once, `0` resets), SMS keywords, report idempotency, ETag 304 and i18n key parity.
- `uvicorn app.main:app --reload`, then open `/docs`, walk through the USSD flow with curl, and check `CHECK MAIZE 700`.

## Step 1 status: backend MVP done
- All endpoints above work on SQLite with seed data. `/docs` is live for the frontend team.
- Seed data is labeled `source=seed` and regenerated relative to today. It gets replaced as the data team imports real CSVs.
- **Open items:** an Acholi native speaker must review `backend/app/i18n/ach.py`. The transport rate (2 UGX/kg/km) and trader margin (20%) are assumptions in `config.py` and can be tuned with env vars.
- **Not in the MVP:** Dockerfile and compose (part of Step 2), LLM, Azure Maps, Africa's Talking gateway (the `SmsGateway` protocol is ready for it).

## Next steps (after MVP)
2. Azure: Container Apps (`az containerapp up`) + Azure SQL serverless, then connect the GitHub repo (deploy on push).
3. Functions timer → `/admin/refresh` daily, `/admin/briefs/generate` + `/broadcast` weekly.
4. Azure OpenAI: kiosk brief narrative; optional extraction from unstructured text.
5. ⏰ Collective selling calculator · Azure Maps routes · QR Fair Price Ticket · demo script.
