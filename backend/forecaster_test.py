import sys, asyncio, traceback
sys.path.insert(0, '.')

async def test():
    print("=== STEP 1: import modules ===")
    try:
        from app.api.stock_data import fetch_chart
        from app.api.technical_analysis import compute_technical_analysis
        from app.api.forecaster import build_features, StockForecaster
        print("imports OK")
    except Exception as e:
        print("IMPORT ERROR:", e)
        traceback.print_exc()
        return

    print("=== STEP 2: fetch chart ===")
    try:
        chart = await fetch_chart("RELIANCE.NS", interval="5m", range_="5d")
        print("chart error:", chart.get("error"))
        candles = chart.get("candles", [])
        print("candles count:", len(candles))
    except Exception as e:
        print("CHART ERROR:", e)
        traceback.print_exc()
        return

    if len(candles) < 30:
        print("FAIL: not enough candles:", len(candles))
        return

    print("=== STEP 3: compute TA ===")
    try:
        ta = compute_technical_analysis(candles)
        print("ta error:", ta.get("error"))
        print("ta score:", ta.get("score"))
    except Exception as e:
        print("TA ERROR:", e)
        traceback.print_exc()
        return

    print("=== STEP 4: build features ===")
    try:
        feats = build_features(candles, ta)
        print("features shape:", feats.shape if feats is not None else None)
        print("features sample:", feats[:5] if feats is not None else None)
    except Exception as e:
        print("FEATURES ERROR:", e)
        traceback.print_exc()
        return

    print("=== STEP 5: train model ===")
    try:
        fc = StockForecaster("RELIANCE")
        ta_history = []
        for i in range(30, min(80, len(candles))):
            snap = compute_technical_analysis(candles[:i])
            ta_history.append(snap if not snap.get("error") else ta)
        print("ta_history len:", len(ta_history))
        trained = fc.train(candles[:80], ta_history)
        print("trained:", trained)
    except Exception as e:
        print("TRAIN ERROR:", e)
        traceback.print_exc()
        return

    if trained:
        print("=== STEP 6: predict ===")
        try:
            pred = fc.predict(candles, ta)
            print("prediction:", pred)
        except Exception as e:
            print("PREDICT ERROR:", e)
            traceback.print_exc()

asyncio.run(test())
