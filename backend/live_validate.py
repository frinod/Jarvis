"""
Live pipeline validation — RELIANCE single-stock test.
Run: python live_validate.py
"""
import asyncio, datetime, time, os, pickle, sys

SYMBOL = "RELIANCE"
HORIZON = 30  # minutes


async def main():
    # ── STEP 1: Market session ────────────────────────────────
    print("=" * 60)
    print("STEP 1 — MARKET SESSION")
    print("=" * 60)
    now_utc = datetime.datetime.utcnow()
    ist = now_utc + datetime.timedelta(hours=5, minutes=30)
    h, m = ist.hour, ist.minute
    total = h * 60 + m
    wd = ist.weekday()
    DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    if wd >= 5:
        sess = "CLOSED (Weekend)"
    elif total < 540:
        sess = "CLOSED (Pre-market)"
    elif total < 555:
        sess = "PRE_MARKET (09:00-09:15)"
    elif total <= 930:
        sess = "OPEN"
    elif total <= 960:
        sess = "POST_MARKET (15:30-16:00)"
    else:
        sess = "CLOSED (After hours)"
    print(f"IST:     {ist.strftime('%Y-%m-%d %H:%M')}")
    print(f"Weekday: {DAYS[wd]}")
    print(f"SESSION: {sess}")
    if "OPEN" not in sess:
        print("\nSTOP: Market not open. Aborting live validation.")
        return

    # ── STEP 2: Model check ───────────────────────────────────
    print()
    print("=" * 60)
    print("STEP 2 — MODEL CHECK: RELIANCE_h6_xgb")
    print("=" * 60)
    model_path = os.path.join("models", "RELIANCE_h6_xgb.pkl")
    meta_path  = os.path.join("models", "RELIANCE_h6_xgb.meta")
    if not os.path.exists(model_path):
        print("ERROR: Model file not found")
        return
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    meta_ts = float(open(meta_path).read().strip()) if os.path.exists(meta_path) else 0
    trained_dt = datetime.datetime.utcfromtimestamp(meta_ts) if meta_ts else None
    age_h = (time.time() - meta_ts) / 3600 if meta_ts else 999
    print(f"Model file:  {model_path}")
    print(f"Model type:  {type(model).__name__}")
    print(f"Trained at:  {trained_dt} UTC" if trained_dt else "Trained at:  unknown")
    print(f"Model age:   {age_h:.1f} hours")
    try:
        print(f"Features:    {model.n_features_in_}")
    except Exception:
        print("Features:    unknown")

    # ── STEP 3: Live market data ──────────────────────────────
    print()
    print("=" * 60)
    print("STEP 3 — LIVE MARKET DATA: RELIANCE.NS")
    print("=" * 60)
    t0 = time.time()
    from app.market_data.service import fetch_candles, initialise
    await initialise()
    chart = await fetch_candles("RELIANCE.NS", interval="5m", days=10)
    latency = round((time.time() - t0) * 1000)
    if chart.get("error"):
        print(f"DATA ERROR: {chart['error']}")
        return
    candles = chart.get("candles", [])
    print(f"Provider:    {chart.get('source', 'unknown')}")
    print(f"Candles:     {len(candles)}")
    print(f"Latency:     {latency}ms")
    print(f"Cached:      {chart.get('cached', False)}")
    print(f"Quality:     {chart.get('quality', '?')}")
    data_status = "UNKNOWN"
    if candles:
        last = candles[-1]
        last_ts_ms = last.get("t", 0)
        last_dt = datetime.datetime.utcfromtimestamp(last_ts_ms / 1000) if last_ts_ms else None
        last_ist = last_dt + datetime.timedelta(hours=5, minutes=30) if last_dt else None
        age_min = (time.time() - last_ts_ms / 1000) / 60 if last_ts_ms else 999
        print(f"Latest IST:  {last_ist.strftime('%Y-%m-%d %H:%M') if last_ist else 'unknown'}")
        print(f"Candle age:  {age_min:.1f} minutes")
        print(f"OHLCV:       O={last['o']} H={last['h']} L={last['l']} C={last['c']} V={last['v']}")
        data_status = "LIVE" if age_min < 15 else "STALE" if age_min < 60 else "OLD"
        print(f"DATA_STATUS: {data_status}")
    if chart.get("warnings"):
        print(f"Warnings:    {chart['warnings']}")

    # ── STEP 4: Full forecast pipeline ───────────────────────
    print()
    print("=" * 60)
    print("STEP 4 — FULL FORECAST PIPELINE: RELIANCE")
    print("=" * 60)
    t1 = time.time()
    from app.api.forecaster import forecast
    result = await forecast(SYMBOL, horizon=HORIZON)
    fc_latency = round((time.time() - t1) * 1000)
    print(f"Forecast latency: {fc_latency}ms")
    if result.get("error"):
        print(f"FORECAST ERROR: {result['error']}")
        if result.get("reason"):
            print(f"Reason: {result['reason']}")
        return
    fc  = result.get("forecast", {})
    reg = result.get("regime", {})
    mtf = result.get("mtf", {})
    val = result.get("validation", {})
    dq  = result.get("data_quality", {})
    ctx = result.get("context", {})
    print(f"Direction:    {fc.get('direction')}")
    print(f"Confidence:   {fc.get('confidence')}%")
    print(f"Prob UP:      {fc.get('prob_up')}%")
    print(f"Prob DOWN:    {fc.get('prob_down')}%")
    print(f"Prob FLAT:    {fc.get('prob_flat')}%")
    print(f"Model:        {fc.get('model')}")
    print(f"Horizon:      {fc.get('horizon')}")
    print(f"Price:        {fc.get('current_price')}")
    print(f"Target:       {fc.get('estimated_target')}")
    print(f"Stop:         {fc.get('estimated_low')}")
    print(f"Candles used: {result.get('candles_used')}")
    print(f"Model trained:{result.get('model_trained')}")
    print()
    print(f"Regime:       {reg.get('regime')} — {reg.get('label')}")
    print(f"Regime adj:   {reg.get('adjusted')}")
    if reg.get("warning"):
        print(f"Regime warn:  {reg['warning']}")
    print()
    print(f"MTF confluence: {mtf.get('confluence')}")
    print(f"MTF score:      {mtf.get('score')}")
    print(f"MTF HTF signal: {mtf.get('htf_signal')}")
    print()
    print(f"WFV accuracy:   {val.get('wfv_accuracy')}%")
    print(f"WFV useful:     {val.get('wfv_useful')}")
    print(f"WFV samples:    {val.get('test_samples')}")
    print()
    print(f"Data quality:   {dq.get('score')}")
    if dq.get("warnings"):
        print(f"DQ warnings:    {dq['warnings']}")
    print()
    print(f"TA trend:       {ctx.get('trend')}")
    print(f"TA signal:      {ctx.get('overall_signal')}")
    print(f"TA confidence:  {ctx.get('ta_confidence')}%")
    print(f"RSI:            {ctx.get('rsi')}")
    print(f"ATR:            {ctx.get('atr')}")
    print(f"Supertrend:     {ctx.get('supertrend')}")
    print(f"Ichimoku bias:  {ctx.get('ichimoku_bias')}")

    # ── STEP 5: Agent pipeline ────────────────────────────────
    print()
    print("=" * 60)
    print("STEP 5 — AGENT PIPELINE")
    print("=" * 60)
    from app.ai.prediction.forecasting import ForecastResult
    from app.ai.agents.trader import TraderAgent, SignalDirection
    from app.ai.agents.analyst import AnalystAgent
    from app.ai.runtime.context import ExecutionContext
    fr = ForecastResult.from_dict(result)
    print(f"ForecastResult.is_valid:      {fr.is_valid}")
    print(f"ForecastResult.direction:     {fr.direction}")
    print(f"ForecastResult.trade_signal:  {fr.trade_signal}")
    print(f"ForecastResult.confidence:    {fr.confidence}")
    print(f"ForecastResult.regime:        {fr.regime}")
    print(f"ForecastResult.mtf_confluence:{fr.mtf_confluence}")
    print(f"ForecastResult.wfv_accuracy:  {fr.wfv_accuracy}")
    ctx_agent = ExecutionContext(user_input="analyse RELIANCE", session_id="live_test")
    ctx_agent.active_goal = "analyse RELIANCE"
    ctx_agent.metadata["_forecast"] = fr
    trader = TraderAgent()
    t_result = await trader.execute(ctx_agent)
    signal = t_result.metadata.get("trade_signal")
    print(f"\nTraderAgent direction:   {signal.direction if signal else 'NONE'}")
    print(f"TraderAgent confidence:  {t_result.confidence}")
    if signal:
        print(f"TraderAgent rationale:   {signal.rationale[:140]}...")
    analyst = AnalystAgent()
    a_result = await analyst.execute(ctx_agent)
    print(f"\nAnalystAgent confidence: {a_result.confidence}")
    print(f"AnalystAgent explanation:{a_result.explanation[:180]}...")

    # ── STEP 6: AI Discovery summary ─────────────────────────
    print()
    print("=" * 60)
    print("STEP 6 — AI DISCOVERY RESULT (1 stock)")
    print("=" * 60)
    direction = fc.get("direction", "FLAT")
    signal_str = "BUY" if direction == "UP" else "SELL" if direction == "DOWN" else "HOLD"
    price_val = fc.get("current_price") or 1
    stop_val  = fc.get("estimated_low") or price_val
    tgt_val   = fc.get("estimated_target") or price_val
    risk   = abs(price_val - stop_val)
    reward = abs(tgt_val - price_val)
    rr = round(reward / risk, 2) if risk else 0
    sigs = result.get("signals_summary", [])
    print(f"SYMBOL:      RELIANCE")
    print(f"PRICE:       {price_val}")
    print(f"DIRECTION:   {direction}")
    print(f"SIGNAL:      {signal_str}")
    print(f"CONFIDENCE:  {fc.get('confidence')}%")
    print(f"REGIME:      {reg.get('regime')}")
    print(f"MTF:         {mtf.get('confluence')}")
    print(f"MODEL:       RELIANCE_h6_xgb (XGBoost)")
    print(f"DATA:        {data_status}")
    print(f"WFV ACC:     {val.get('wfv_accuracy')}%")
    print(f"ENTRY:       {price_val}")
    print(f"STOP:        {stop_val}")
    print(f"TARGET:      {tgt_val}")
    print(f"R:R:         1:{rr}")
    print(f"TOP SIGNALS: {[s['indicator']+':'+s['signal'] for s in sigs[:4]]}")

    # ── STEP 7: Paper trade proposal ─────────────────────────
    print()
    print("=" * 60)
    print("STEP 7 — PAPER TRADE PROPOSAL (NO REAL ORDER)")
    print("=" * 60)
    print(f"Symbol:     RELIANCE")
    print(f"Direction:  {signal_str}")
    print(f"Entry:      Rs.{price_val}")
    print(f"Stop Loss:  Rs.{stop_val}")
    print(f"Target:     Rs.{tgt_val}")
    print(f"R:R:        1:{rr}")
    print(f"Confidence: {fc.get('confidence')}%")
    print(f"Model:      RELIANCE_h6_xgb (XGBoost)")
    print(f"Regime:     {reg.get('regime')}")
    print(f"MTF:        {mtf.get('confluence')}")
    print(f"Timestamp:  {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("NOTE: Paper trade only. No real order placed.")

    # ── STEP 8: 3-stock test ──────────────────────────────────
    print()
    print("=" * 60)
    print("STEP 8 — 3-STOCK TEST (ICICIBANK, TCS, INFY)")
    print("=" * 60)
    test_stocks = ["ICICIBANK", "TCS", "INFY"]
    for sym in test_stocks:
        t_s = time.time()
        try:
            r = await forecast(sym, horizon=30)
            lat = round((time.time() - t_s) * 1000)
            if r.get("error"):
                print(f"  {sym}: ERROR={r['error']} ({lat}ms)")
            else:
                f2 = r.get("forecast", {})
                print(f"  {sym}: {f2.get('direction')} {f2.get('confidence')}% | "
                      f"regime={r.get('regime',{}).get('regime')} | "
                      f"mtf={r.get('mtf',{}).get('confluence')} | "
                      f"wfv={r.get('validation',{}).get('wfv_accuracy')}% | "
                      f"{lat}ms")
        except Exception as e:
            print(f"  {sym}: EXCEPTION={e}")

    # ── STEP 9: Request metrics ───────────────────────────────
    print()
    print("=" * 60)
    print("STEP 9 — REQUEST METRICS")
    print("=" * 60)
    print(f"Data fetch latency:     {latency}ms")
    print(f"Full forecast latency:  {fc_latency}ms")
    print(f"Data cached:            {chart.get('cached', False)}")
    print("Requests per symbol:    ~4-6 (5m candles + regime NIFTY + MTF 1h/4h/1d)")
    print("Note: MTF makes additional candle requests for higher timeframes")

    # ── STEP 9: Model coverage ────────────────────────────────
    print()
    print("=" * 60)
    print("STEP 9 — MODEL COVERAGE")
    print("=" * 60)
    import glob
    pkls = glob.glob("models/*_xgb.pkl")
    symbols_with_models = sorted(set(
        os.path.basename(p).replace("_h3_xgb.pkl","").replace("_h6_xgb.pkl","")
        for p in pkls
    ))
    print(f"Total model files:  {len(pkls)}")
    print(f"Unique symbols:     {len(symbols_with_models)}")
    print(f"Symbols: {symbols_with_models}")

    print()
    print("=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)
    checks = [
        ("Market OPEN",           "OPEN" in sess),
        ("Model loaded",          True),
        ("Live data received",    len(candles) > 0),
        ("Data LIVE/STALE",       data_status in ("LIVE", "STALE")),
        ("Forecast produced",     not result.get("error")),
        ("Real XGBoost model",    result.get("model_trained", False)),
        ("ForecastResult valid",  fr.is_valid),
        ("TraderAgent signal",    signal is not None),
        ("AnalystAgent ran",      a_result is not None),
    ]
    for label, ok in checks:
        print(f"  [{'✓' if ok else '✗'}] {label}")


if __name__ == "__main__":
    asyncio.run(main())
