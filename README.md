# Fair Value (FairPrice)

**Know your crop's value before you sell.**

Fair Value gives smallholder farmers in Northern Uganda a trusted, dated reference price for their produce, at a community kiosk and by SMS on any basic phone, so they can push back on low offers from traders.

▶️ **Demo video:** [Watch on Google Drive](https://drive.google.com/file/d/1HfiSlsyNXDgwUzLAxc0_Cpnih2pKm_63/view)

Built for the BCG hackathon ("World Hunger") around the persona of Clara, a smallholder farmer in the Acholi/Lango region.

---

## What we built

### 1. Farmer kiosk (tablet, no account or phone needed)

- **Choose a language:** English or Kiswahili (the **English / Kiswahili** button switches at any time; **Home** goes back to the start).
- **Choose a category and crop:** photo tiles for vegetables and grains.
- **See three grade cards (A, B, C):** each with a photo, three short quality points and the **price in UGX per kg**, plus the market and the month the price was recorded.
- Works offline for crops already opened once (service worker + saved records).

Supported crops: **beans, maize, sorghum, millet, fresh cassava and leafy vegetables**.

### 2. Fair Value Updates: SMS price announcements

Kiosk staff can text farmers the latest prices in one message, in English or Kiswahili:

```
Fair Value Updates
Price for 1 kg in Uganda shillings (UGX)
Grade A = best, B = good, C = lower quality

VEGETABLES
Fresh cassava: A UGX 561, B UGX 539, C UGX 509
Leafy vegetables: A UGX 1,821, B UGX 1,751, C UGX 1,655

FRUITS: No changes

GRAINS/CROPS
Beans: A UGX 3,762, B UGX 3,617, C UGX 3,418
Maize: A UGX 1,725, B UGX 1,659, C UGX 1,568
Sorghum: A UGX 1,738, B UGX 1,671, C UGX 1,579
Millet: A UGX 2,678, B UGX 2,575, C UGX 2,433

Market prices from Aug 2026.
```

- Sent through **BulkSMS**; works on any phone, no data or app needed.
- When forecasts are available, each crop also shows a one-word trend: *rising*, *falling* or *steady*.
- A category with no new prices says **"No changes"**.

### 3. Kiosk staff screen

Opened from **Kiosk staff** in the footer. Fully bilingual (English / Kiswahili).

- **Fair Value Updates** (at the top):
  - Saved **recipients checklist**: tick **Everyone (bulk)** or pick individual people.
  - **Add** a recipient with name, number and an "agreed to receive SMS" tick. Local numbers (e.g. `072…`) are converted to international format automatically. **Remove** with one click.
  - Choose the message language, press **Send Updates**, check the exact SMS preview, then **Confirm and send**. Results show sent / skipped / failed per number.
- **Device setup** (collapsed): kiosk name, default market, starting language, idle reset time.

On the kiosk computer itself the staff key is filled in automatically. On any other device, or through a public link, staff type it.

---

## Where the prices come from

- **Source:** WFP food price data for Uganda, published on HDX (Humanitarian Data Exchange), filtered to Northern Uganda districts (Acholi, Lango, West Nile, Karamoja).
- **Market price:** the most recent monthly observation per market; retail prices are converted to wholesale-level market prices with per-crop factors (see `ml/README.md`).
- **Grades:** A / B / C = **1.04 / 1.00 / 0.945 ×** the market price. These are app estimates, not official premiums.
- **Forecasts:** a **LightGBM** model trained on the historical monthly series predicts next month's price. On the last 12 test months it scored **16.7% MAPE vs 18.5%** for the naive "same as last month" baseline.
- **Never invented:** prices and SMS texts are built only from these published records and saved model outputs. No AI-generated prices.
- An optional source refresh re-checks HDX and only publishes new data after schema, unit, date, coverage and anomaly checks.

---

## Run it locally

Requires Python 3.12+ on Windows (PowerShell shown).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe tools/configure_local.py      # creates a private staff key in .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

- Kiosk: http://127.0.0.1:8000/
- API docs: http://127.0.0.1:8000/docs

The backend serves the kiosk UI and the API from one server, using a local SQLite database.

### Settings (`.env`, never committed)

| Setting | Purpose |
|---|---|
| `ADMIN_TOKEN` | Staff key for the Kiosk staff screen and SMS endpoints (created by `tools/configure_local.py`) |
| `BULKSMS_TOKEN_ID`, `BULKSMS_TOKEN_SECRET` | BulkSMS API token. Without them, SMS runs as a preview only |
| `BULKSMS_MAX_PARTS` | Max SMS parts per message. The farmer update needs **4** |
| `COMMS_ALLOWED_RECIPIENTS` | Optional testing guard: comma-separated numbers allowed to receive SMS. Empty = anyone |
| `SMS_DEFAULT_COUNTRY_CODE` | Country code for local numbers typed by staff (default `+256`, Uganda) |
| `SOURCE_REFRESH_ENABLED` | Turn on the scheduled WFP/HDX source check |

### Share a public demo link

GitHub Pages can't run the FastAPI backend, so for a quick public link we tunnel the local server with [ngrok](https://ngrok.com):

```powershell
ngrok http 8000
```

Visitors click **Visit Site** once on the ngrok notice. The link only works while the computer and server are running.

---

## SMS API (kiosk staff)

All endpoints need the staff key in the `X-Admin-Token` header.

| Endpoint | What it does |
|---|---|
| `POST /api/sms/farmers` | Fair Value Updates. `{"phones": ["+256…"], "language": "en" or "sw", "dry_run": true}`. Set `"dry_run": false, "consent_confirmed": true` to send |
| `GET /api/sms/contacts` | List saved recipients |
| `POST /api/sms/contacts` | Save a recipient: `{"name": "…", "phone": "0772…", "consent": true}` |
| `DELETE /api/sms/contacts/{id}` | Remove a recipient |

Every real send is logged in the `sms_outbox` table. Saved recipients live only in the local database.

---

## Project layout

| Folder | What lives there |
|---|---|
| `backend/` | FastAPI app: kiosk API, SMS updates (BulkSMS), recipients, source refresh; serves the frontend |
| `frontend/` | Kiosk web app (plain HTML/CSS/JS, offline-capable service worker) |
| `ml/` | WFP/HDX ingestion, features, LightGBM training, backtest and saved artifacts |
| `tools/` | `configure_local.py` local setup helper |
| `docs/` | Data sources, farmer flow notes, model verification |

---

## Limitations and next steps

- **Price freshness:** the latest published data is monthly (currently August 2026). Next: weekly prices reported by kiosk staff or market agents.
- **Language:** Kiswahili is supported, but most farmers in Northern Uganda speak Acholi/Luo. Next: Acholi support, and a native-speaker review of the Kiswahili text.
- **Grades:** A/B/C prices are fixed multipliers, not verified buyer premiums. Next: check them against real buyer prices.
- **Fruit and trends:** no fruit data yet; trend words appear only when the model forecasts match the current data.
- **Reaching a sale:** Fair Value tells farmers the fair price; connecting them to vetted buyers is the next step.
- **SMS cost:** the full update is 4 SMS parts per farmer.
