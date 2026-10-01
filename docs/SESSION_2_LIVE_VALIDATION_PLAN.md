# SESSION 2 — LIVE VALIDATION PLAN

Status: PENDING — NSE market closed / Angel One rate limited
Created: Session 2 pause checkpoint
Do not execute until NSE market is open and provider access is confirmed.

---

## LIVE VALIDATION OBJECTIVE

Prove that JARVIS can obtain live market data and pass it through the full
production pipeline end-to-end:

```
Angel One / Yahoo provider
    ↓
candles (real, fresh, market-hours)
    ↓
technical analysis
    ↓
feature engineering
    ↓
real XGBoost model (.pkl)
    ↓
forecast (direction, confidence, probabilities)
    ↓
regime filter
    ↓
MTF analysis
    ↓
ForecastResult
    ↓
TraderAgent / AnalystAgent (via ctx.metadata["_forecast"])
    ↓
AI Discovery recommendation
```

This is a SOFTWARE CORRECTNESS test, not a prediction quality test.
The question being answered is: does the real-world data → model → JARVIS
path execute without errors and produce a structurally valid result?

---

## TEST SIZE — START SMALL

### Step 1: ONE stock
- Symbol: RELIANCE (or whichever has a trained .pkl in backend/models/)
- Do NOT start with the full Nifty 50 scan
- Confirm the full pipeline executes for that one symbol
- Record all fields listed in the checklist below

### Step 2: 2–3 stocks
- Only after Step 1 succeeds without errors
- Choose symbols from different sectors
- Confirm results are structurally consistent

### Step 3: Larger universe (optional, separate session)
- Only after Steps 1 and 2 succeed
- Evaluate request volume and rate-limit behaviour before proceeding
- Do NOT run the full 50-stock AI Discovery scan until the
  request-deduplication architecture issue is resolved (see Session 3)

---

## LIVE TEST CHECKLIST — RECORD FOR EACH SYMBOL

| Field                  | Expected                          | Actual |
|------------------------|-----------------------------------|--------|
| symbol                 | e.g. RELIANCE                     |        |
| provider used          | AngelOne or Yahoo                 |        |
| candle interval        | 5m or 15m                         |        |
| candle count           | ≥ 26                              |        |
| latest candle timestamp| within current session            |        |
| market data freshness  | ≤ 5 min old during market hours   |        |
| model file used        | RELIANCE_h6_xgb.pkl (or similar)  |        |
| model version          | from .meta file if available      |        |
| prediction direction   | UP / DOWN / FLAT                  |        |
| confidence             | 0–100 (not 0.0, not hardcoded)    |        |
| prob_up                | 0–100                             |        |
| prob_down              | 0–100                             |        |
| prob_flat              | 0–100                             |        |
| regime                 | bull_trend / bear_trend / etc.    |        |
| MTF confluence         | strong / moderate / weak / None   |        |
| final agent signal     | BUY / SELL / HOLD                 |        |
| request count          | record total provider calls made  |        |
| latency (ms)           | end-to-end for one symbol         |        |
| provider errors        | none / rate_limit / access_denied |        |
| fallback events        | AngelOne→Yahoo fallback? Y/N      |        |

---

## SAFETY RULES

### Stale / missing / incomplete data
If market data is stale, missing, or the provider returns an error:
- Return `NO_TRADE / DATA_UNAVAILABLE`
- Do NOT generate a confident directional recommendation
- Do NOT fabricate values

### Rate limit
If Angel One returns "Access denied because of exceeding access rate":
- Record the event
- Stop the test immediately
- Do NOT retry in a loop
- Classify as: `LIVE PROVIDER RATE LIMITED — not a forecasting failure`

### Market closed
If candles are stale because the market is closed:
- Classify as: `LIVE PROVIDER VALIDATION PENDING — MARKET CLOSED`
- Do NOT classify as: `Forecasting failed`
- These are different conditions

---

## PAPER TRADING CONSTRAINT

Even if the live forecast pipeline works correctly:
- The first execution test MUST remain PAPER TRADING
- No broker order placement
- No real-money execution
- Validate the signal output only

---

## WHAT SUCCESS LOOKS LIKE

A passing live validation means ALL of the following are true:

1. Provider returned fresh candles (timestamp within current session)
2. Technical analysis computed without error
3. XGBoost model loaded and produced a prediction (not UNAVAILABLE)
4. ForecastResult.is_valid == True
5. TraderAgent produced BUY, SELL, or HOLD (not an exception)
6. AnalystAgent produced a confidence value derived from the forecast
   (not 0.5 fallback, not 0.7 hardcoded)
7. AI Discovery returned a structurally valid result dict with
   model_direction, model_confidence, forecast_source == "xgboost"
8. No unhandled exceptions in the pipeline
9. Request count is reasonable (< 10 for a single symbol)

---

## WHAT FAILURE LOOKS LIKE — AND HOW TO CLASSIFY IT

| Symptom                              | Correct classification                        |
|--------------------------------------|-----------------------------------------------|
| Angel One returns 429 / access denied| PROVIDER RATE LIMITED — not a model failure   |
| Yahoo returns stale/empty candles    | MARKET CLOSED / DATA UNAVAILABLE              |
| Model file not found                 | MODEL MISSING — check backend/models/         |
| ForecastResult.is_valid == False     | FORECAST PIPELINE ERROR — check forecaster.py |
| Agent returns HOLD with conf=0.0     | NO FORECAST INJECTED — check _analyze() wiring|
| Exception in _analyze()              | INTEGRATION BUG — check market_intelligence.py|

Do not conflate provider failures with model failures.
Do not conflate market-closed conditions with software bugs.
