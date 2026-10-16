# ML: Northern Uganda price model

Gives a **market price** (UGX/kg) for each farm product and market in Northern Uganda, now and forecast for next month, from WFP data on HDX.

**Products:** beans, maize, sorghum, millet, cassava (fresh), leafy vegetables.
**Area:** Acholi, Lango, West Nile and Karamoja districts. Acholi and Lango (Clara's area) are flagged `core_area`.

## Run it

From the repo root:

```bash
pip install -r ml/requirements.txt
python ml/ingest_wfp.py      # clean CSV -> ml/data/processed/prices_monthly.csv
python ml/train.py           # test, train, write snapshot + metrics
python ml/backtest.py        # optional: rolling 12-month backtest
```

`ingest_wfp.py` looks for `wfp_food_prices_uga.csv` in `ml/data/raw/` first, then the repo root. Use `--input <path>` for anywhere else.

## Files

| File | What it does |
|---|---|
| `config.py` | Districts, products, paths, settings. Change products or markets here. |
| `ingest_wfp.py` | Keeps northern districts and our products, UGX per kg, one price per month. |
| `features.py` | Lags, trends, seasonality and regional averages; target = next month's log price change. |
| `market_price.py` | Turns WFP retail prices into market prices (see below). |
| `train.py` | Tests on the last 12 months vs a naive baseline, retrains, writes outputs. |
| `backtest.py` | Retrains every month for the last 12 months and scores each forecast. |
| `show_prices.py` | Prints prices per product, per market, or one market's history + forecast. |

## Outputs (`ml/artifacts/`)

| File | Used by |
|---|---|
| `model.pkl` | `backend/app/services/forecast.py` (what-if forecasts) |
| `price_snapshot.json` / `.csv` | API: one row per product × market × price type, with last real price, date, forecast, change %, source |
| `crop_prices.json` | Kiosk/SMS headline: one Northern Uganda price per product, plus core markets |
| `metrics.json` | Admin page: model vs baseline MAPE, overall and per product |
| `market_price_factors.json` | Admin page: the retail-to-market factor per product and the data behind it |
| `backtest_predictions.csv` | Admin chart: forecast vs actual per month |

## How retail becomes market price

WFP records mostly **retail** prices (what shoppers pay a stall in town). Produce sells at the market at the **wholesale** level, which is lower. So every final price is:

```
market price = retail price x factor
```

- **Beans (x0.842) and maize (x0.883): measured.** WFP recorded both retail and wholesale prices in Lira for the same months (126 and 129 months, 2011–2022). The factor is the median of wholesale ÷ retail.
- **Sorghum, millet, cassava, leafy vegetables (x0.875): assumed.** No wholesale data exists for them, so they use the median of all measured months (beans + maize together).
- Rows that already are wholesale prices are used as they are.
- To show retail instead, set `FINAL_PRICE_BASIS = "retail"` in `config.py`.

The model is trained and tested on the real retail series; the factor is applied afterwards, so it does not change forecast accuracy.

## Honesty rules

- Every price carries its market, month and source. Forecasts never hide the last real price.
- A product only uses the model if it beat the naive baseline ("next month = this month") on the test months; otherwise `forecast_method` is `naive`.
- Series with no price in the last 6 months are marked `stale` (millet currently ends in Jan 2026).
- Every output keeps the observed retail price next to the market price, and says whether its factor is measured or assumed.
- Market price is still not farm-gate. Transport from the village and the grade factor are applied in `backend/app/services/pricing.py`.
