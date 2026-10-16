# FairPrice: Hackathon Plan (World Hunger: Market Price Transparency)

> This is the working plan for the project. We build one step at a time and mark progress here.
>
> **Progress:** ✅ Step 0 (skeleton) · ⬜ Step 1 · ⬜ Step 2 · ⬜ Step 3 · ⬜ Step 4 · ⬜ Step 5 · ⬜ Step 6 · ⬜ Step 7

## Context
Clara Commune runs 30 village groups in Northern Uganda. Her farmers sell produce at about ⅓ of what it fetches in Gulu, Lira or Kenya, because brokers control price information and grade quality subjectively. We have under 20 hours to build a working demo, with no slides. The repo is empty apart from the initial commit (`README.md`), so we build from scratch.

**Product name:** **FairPrice**. It matches the repo and the line "When families earn fairly…". The design rule throughout: **the farmer's price must be explainable and verifiable, not just "AI-predicted".**

---

## 1. Critique: what's strong, and what would lose us points

**Strong:** the 2-channel design (kiosk + feature phone) fits the device divide. Offline-first, Category A/B transparency and transport-netted prices are all correct instincts.

**Fatal flaws / blind spots to fix:**
1. **"Predicted price" alone won't stop low-balling.** A broker can say "your AI is wrong". The fix is to anchor every number to **observed market data with a source and a date**. On top of that we derive one actionable number, the **Walk-Away Price (fair floor)**:
   `floor/kg = predicted town price (grade-adjusted) − transport cost/kg (Azure Maps) − fair trader margin (~20%, configurable)`
   We also show the broker's resale value ("This sack sells for UGX 1,450/kg in Lira today"). Farmers then negotiate from a number, not a feeling.
2. **Data reality: real sources exist, so use them:**
   - **WFP VAM food prices (HDX CSVs) for Uganda and Kenya.** Monthly retail/wholesale prices by market (Gulu, Lira, Kampala, Kisumu, Nairobi…) for maize, beans, sorghum, cassava, bananas and more. Downloadable now. **This is the primary training set.**
   - **FEWS NET / FAO GIEWS FPMA** for cross-checking. **KAMIS (Kenya)** for horticulture such as tomatoes and avocado. **UCDA monthly reports** for coffee.
   - Gaps (avocado in Uganda, Category B prices) are filled by documented assumptions (`grade_factor` per crop, e.g. B = 0.6–0.75 × A). Stated honestly in the UI as "estimate". Judges reward honesty plus a path to real data.
   - Real data is mostly **monthly**, so don't over-claim daily ML. Present it as **"monthly real data + weekly crowdsourced field reports + model nowcast"**.
3. **Keeping it live ("who maintains it?")** is solved with a closed data loop and no farmer effort:
   - An **Azure Functions timer** (daily) pulls the HDX/WFP CSVs, upserts them into Azure SQL, retrains or refreshes predictions, and writes a `price_snapshot` table that the API serves.
   - **Field price reports by SMS** from Clara's 30 group leaders and kiosk attendants (`REPORT MAIZE A 1200 GULU`). Stored as `field_reports` and weighted into the nowcast. Outliers are auto-flagged (z-score) for admin review.
   - A **minimal admin page** (developers/BCG) shows source freshness, flagged reports and the grade factors. That's the maintenance story.
4. **Missed impact lever: collective selling.** One farmer can't afford transport to Lira, but a group pooling 2 tonnes can. A **Group Bulk-Sale calculator** (pooled kg → best market net per farmer) is the realistic way the "⅓ price" gap gets closed. Clara's role is literally group lead, so lean on her.
5. **Category B = food-waste story.** Never show B as just "a lower price". Show **"Sell within 48h → nearest local market / processor"** with its net price, so B produce gets sold instead of rotting. This is our World Hunger point.
6. **Measurable impact:** compute it live in the demo from transparent assumptions, e.g. `extra income = (floor − typical broker offer) × kg`, aggregated over 30 groups × members × seasons. Add a **model backtest (MAPE vs. naive last-price baseline)** shown on the admin page. Real metrics beat claimed metrics.
7. **LLMs must never generate prices.** Prices come from SQL plus the model, deterministically. The LLM only understands, explains and translates. Say this out loud to judges; it shows maturity.
8. **Acholi caveat:** LLM Acholi is unreliable. Use **hardcoded, human-checked templates** for SMS/USSD/UI strings in all 3 languages. Use the LLM for free-text understanding and English/Swahili explanations, and label Acholi LLM output as "beta".
9. **SMS provider:** **Africa's Talking sandbox** works without a Ugandan number. It has a free web simulator for SMS and USSD. Our primary demo will still be our **own in-app feature-phone simulator** calling the same `/sms` and `/ussd` endpoints, so the demo has zero external dependency. AT sandbox is a stretch goal.

## 2. Azure OpenAI: highest impact for the lowest effort
One `services/llm.py` wrapper: Azure OpenAI (gpt-4o-mini) as primary, **Claude API as automatic fallback**, so the demo never dies on quota or access problems.
1. **Negotiation Coach (killer feature).** Farmer or attendant enters "Broker offers 700/kg for 200kg maize". Function calling triggers `get_fair_price(crop, grade, market)`, and the reply comes back: verdict (Fair / Low / Very low), counter-offer, and best alternative market. Works by SMS too: `OFFER MAIZE 700 200`.
2. **Free-text SMS understanding.** "bei ya mahindi Gulu?" or "maize price lira" is intent-parsed into structured params, which go into the same deterministic price lookup and come back as a ≤160-char reply. This lets the system skip the menu for confident users.
3. **Weekly Market Brief.** A Functions timer generates a short per-region advisory ("Beans up 12% in Lira; hold B-grade tomatoes → sell Gulu by Thu"). It's cached in SQL, so it's free to serve offline and can be broadcast as SMS alerts.
4. **(Stretch) Unstructured ingestion.** The LLM extracts price rows from a pasted bulletin PDF or a group-leader WhatsApp message into `field_reports`. This strengthens the "how data stays live" answer.

## 3. Architecture: map from AWS knowledge, avoid config hell

| AWS you know | Azure we use | Notes |
|---|---|---|
| ECR + ECS Fargate / App Runner | **ACR + Azure Container Apps** | `az containerapp up --source ./backend` builds and deploys in one command |
| Lambda + EventBridge cron | **Azure Functions (Python, timer trigger)** | ingestion, retrain, weekly brief, SMS alerts |
| RDS | **Azure SQL Database (serverless, free offer)** | enable "Allow Azure services" firewall rule plus your own IP |
| S3 | Blob Storage | model artifact + grade images (or just bake them into the image) |
| Bedrock | **Azure OpenAI** (via AI Foundry) | **check model deployment access FIRST, tonight** |
| Location Service | **Azure Maps** Route API | precompute village→market distance matrix into SQL (offline + cheap); haversine×1.3 fallback |

**Deployment simplifications (the important part):**
- **One container**: FastAPI serves the API **and** the built React app (static files). One URL, no CORS, no Static Web Apps setup. Multi-stage Dockerfile: node build → python runtime.
- **DB abstraction**: SQLAlchemy plus a `DATABASE_URL` env var. **SQLite locally, Azure SQL in prod**. Build everything locally first; Azure is only the last step.
- **Known pain point:** pyodbc needs **Microsoft ODBC Driver 18** installed in the Dockerfile (`msodbcsql18`). Bake it in from the start. Connection string: `mssql+pyodbc://...?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes`.
- **Model**: train offline (`ml/train.py`) and ship `model.pkl` inside the image. The API serves precomputed `price_snapshot` rows (fast, robust), and inference runs on the fly only for what-if queries.
- Secrets live as Container App secrets/env vars (skip Key Vault tonight).
- Functions share code by importing a small `shared/` package, or simply call the backend's `/admin/refresh` endpoint (simplest; recommended).

```
[Kiosk tablet PWA] ─┐                         ┌─ Azure SQL (prices, snapshots, users, reports, briefs)
[Phone simulator]  ─┼─ HTTPS ─ Container App ─┼─ model.pkl (LightGBM)
[AT SMS/USSD hook] ─┘   (FastAPI + React)     ├─ Azure OpenAI (→ Claude fallback)
                                              └─ Azure Maps (distance matrix, cached)
Azure Functions (timers): daily ingest WFP/HDX → POST /admin/refresh · weekly brief · SMS alerts
```

**Offline-first kiosk:** a PWA (`vite-plugin-pwa`) with a service worker. The last `/snapshot` payload is stored in localStorage/IndexedDB with `generated_at`. The UI shows "Last updated 2h ago · Offline", plus a Refresh button and ▲ green / ▼ red % change vs. last period.

**Hardware toolbox coverage:** Tablet/Smartphone (kiosk PWA), GPS (kiosk/farm location → nearest markets), SMS (feature phones), QR (Fair Price Ticket, below), Solar + PowerBank (kiosk power, offline-first design, low-power dark UI). NFC is mentioned as an alternative ID card.

## 4. Killer demo moments (each ≤3h)
1. **"Text it live" + Negotiation Coach.** On-screen feature-phone simulator: pick Acholi → Fruits → Gulu → get A/B prices. Then type `OFFER MAIZE 700 200` and get back: "Too low. Fair floor 1,050/kg. Lira nets you +UGX 70,000 after transport. Counter at 1,000." Judges see the exact moment a farmer stops being low-balled.
2. **Fair Price Ticket (QR) + "Middleman Gap" map.** The kiosk prints or shows a QR "Fair Price Ticket" (crop, grade, today's floor, timestamp, signed hash). The broker or anyone scans it and sees a verifiable price page. Next to it, an Azure Maps view shows village → Gulu/Lira/Kampala/Kisumu with **net after transport for 200 kg**, highlighting the best market. Finish by **switching wifi off**: the app keeps working with "Offline · last updated".

## 5. Build plan (≈16h, assumes 2–4 people; stop at each checkpoint)

**Step 0 (now, 15 min): PLAN.md + folder skeleton** ← first thing we do on approval.
```
FairPrice/
  PLAN.md  README.md  docker-compose.yml  .env.example  .gitignore
  backend/
    Dockerfile  requirements.txt
    app/
      main.py  config.py  db.py  models.py  schemas.py
      routers/   prices.py  markets.py  sms.py  ussd.py  advisor.py  reports.py  admin.py  ticket.py
      services/  pricing.py (floor formula)  transport.py (Azure Maps + cache)  llm.py (AOAI→Claude)
                 sms_menu.py (state machine)  i18n.py (en/sw/ach templates)  forecast.py (load model.pkl)
      seed/      markets.json  crops.json  grade_factors.json
    tests/
  ml/
    ingest_wfp.py  features.py  train.py  backtest.py
    data/raw/  data/processed/  artifacts/ (model.pkl, metrics.json)
  functions/
    function_app.py (timer: daily_refresh, weekly_brief, price_alerts)  host.json  requirements.txt
  frontend/
    (Vite + React + Tailwind + vite-plugin-pwa)
    src/ i18n/{en,sw,ach}.ts  lib/{api,cache}.ts
         components/{PriceTicker,GradeCard,MarketMap,PhoneSimulator,NegotiationCoach,OfflineBanner,FairPriceTicket,ImpactPanel}
         pages/{Kiosk,Admin,TicketVerify}
    public/grades/  (A/B reference images per crop)
  infra/
    deploy.sh (az cli: rg, acr, sql, containerapp, functionapp)  schema.sql
  docs/
    demo-script.md  data-sources.md
```

**Step 1 (2h): data + model.** Download WFP HDX CSVs for UG + KE and normalize (UGX; KES→UGX via config rate; kg units). Features: market, crop, month, lags (1, 2, 3), rolling mean, region demand proxy. LightGBM vs. naive baseline backtest → `metrics.json`. Produce `price_snapshot` (A/B, Δ%, forecast next period).
**Step 2 (2.5h): backend core.** SQLAlchemy models (`markets, crops, prices, price_snapshot, users(phone, lang, session_state), field_reports, briefs, distance_matrix`), `/snapshot`, `/prices`, `/fair-price`, `/markets/compare`, seed + load script, pytest smoke tests.
**Step 3 (2h): SMS/USSD state machine.** `/sms` + `/ussd` (Africa's Talking-compatible payloads). Language saved once per phone ('0' = change). `REPORT …` and `OFFER …` commands. Free-text → LLM intent.
**Step 4 (3h): kiosk frontend.** Language switcher, ticker cards, A vs. B grade cards with images + bullets, market comparison, offline cache + refresh + last-updated, phone simulator, negotiation coach.
**Step 5 (1.5h): Azure Maps + QR ticket + impact panel.**
**Step 6 (2h): Azure deploy.** SQL, Container App, Functions timer, AOAI. Do a **smoke deploy early (after Step 2)** to flush out config issues.
**Step 7 (1.5h): admin page, weekly brief, polish, demo-script rehearsal ×3, backup recording of the demo.**

Parallel split if 3+ people: A = ML/data (Steps 1, 5 data), B = backend/SMS/Azure (2, 3, 6), C = frontend (4, 5 UI).

## Verification
- `pytest backend/tests` covers the floor formula, the SMS state machine transitions (language persisted, '0' resets) and the snapshot endpoint.
- `docker compose up` brings up the kiosk at localhost, served from the single container. Walk the full demo script locally on SQLite.
- Offline check: load the kiosk, switch the browser to offline in DevTools, reload; it should show cached data and the "last updated" banner.
- `ml/backtest.py` prints MAPE for the model vs. the naive baseline, and the model must beat the baseline (lower MAPE) before we claim it.
- After deploy: hit `/health`, `/snapshot` and `/sms` on the Container App URL. Trigger the Function manually and confirm `price_snapshot.generated_at` updates. Test the LLM fallback by unsetting the AOAI key and checking that Claude answers.

## Risks / do tonight first
1. Confirm Azure subscription credits + **Azure OpenAI model deployment** (if blocked, Claude fallback carries the demo; still show the AOAI code path).
2. Download WFP HDX CSVs (validate that Gulu/Lira/Kisumu coverage exists).
3. Collect A/B reference photos per crop (licensed/CC images) and get an Acholi speaker to check the ~30 template strings, if at all possible.
