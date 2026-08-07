# Architecture Baseline — v0.7.1-trading-verified

**Date**: 2026-08-07  
**Git Tag**: `v0.7.1-trading-verified`  
**Commit**: `cef7a58`  
**Branch**: `master`  
**Tests**: 1517 / 1517 passing  
**Status**: FROZEN — Trading Engine

---

## What This Baseline Represents

This is the first formally verified baseline of the Jarvis project.

It marks the completion of:

- Phase 5 — Configuration Kernel
- Phase 5.5 — Infrastructure Kernel
- Phase 6 — AI Runtime
- V&V Phase — Trading Engine Verification (VV-001 through VV-010)

From this point, the trading engine is frozen. All future AI capabilities are built
**above** this baseline, consuming its outputs rather than modifying its internals.

---

## Architecture at This Baseline

```
┌─────────────────────────────────────────────────────────┐
│                    AI Layer (Phase 7+)                  │
│  Brain · Memory · RAG · Agents · Reasoning · Learning   │
│  Prediction Intelligence · Market Intelligence          │
└────────────────────┬────────────────────────────────────┘
                     │ consumes
┌────────────────────▼────────────────────────────────────┐
│              Trading Services Layer                     │
│  JarvisOrchestrator · AIRuntime · LLMRouter             │
│  MarketDataService · AngelOne · Yahoo Finance           │
└────────────────────┬────────────────────────────────────┘
                     │ consumes
┌────────────────────▼────────────────────────────────────┐
│         Verified Trading Engine  ← FROZEN               │
│                                                         │
│  technical_analysis.py   forecaster.py                  │
│  market_regime.py        mtf_analysis.py                │
│  market_intelligence.py  backtesting.py                 │
│  paper_trading.py        auto_trader.py                 │
│  confidence.py           feature_store.py               │
└─────────────────────────────────────────────────────────┘
```

**Rule**: The AI layer may call any function in the Trading Engine.
It may not modify Trading Engine internals without a new V&V cycle and ADR.

---

## Component Inventory

### Frozen Trading Engine

| File | Purpose | V&V Status |
|------|---------|------------|
| `app/api/technical_analysis.py` | 20+ indicators, candlestick patterns, SMC, chart patterns | VV-001 ✅ |
| `app/api/forecaster.py` | XGBoost price direction forecasting, feature engineering | VV-002 ✅ |
| `app/api/market_intelligence.py` | Movers, heatmap, AI discovery, news, intraday assistant | VV-003 ✅ |
| `app/api/market_regime.py` | NIFTY regime detection, signal filtering | VV-004 ✅ |
| `app/api/mtf_analysis.py` | Multi-timeframe confluence scoring | VV-005 ✅ |
| `app/api/backtesting.py` | Historical strategy replay, performance metrics | VV-006 ✅ |
| `app/api/paper_trading.py` | Virtual portfolio, P&L, charges, Sharpe, drawdown | VV-007 ✅ |
| `app/api/auto_trader.py` | Autonomous scan-enter-monitor-exit loop | VV-008 ✅ |
| `app/ai/prediction/confidence.py` | Multi-source confidence aggregation | VV-009 ✅ |
| `app/ai/prediction/feature_store.py` | Feature vector extraction for ML models | VV-010 ✅ |

### AI Runtime (Phase 6 — Active, Not Frozen)

| Component | File | Status |
|-----------|------|--------|
| Brain | `app/ai/brain/brain.py` | Phase 7 will extend |
| Memory Pipeline | `app/ai/memory/__init__.py` | Phase 7A will replace embeddings |
| Short-Term Memory | `app/ai/memory/short_term.py` | Phase 7A will extend |
| Long-Term Memory | `app/ai/memory/long_term.py` | Phase 7A: Qdrant replaces |
| Embeddings | `app/ai/memory/embeddings.py` | Phase 7A: sentence-transformers replaces |
| Chain of Thought | `app/ai/reasoning/chain.py` | Phase 7C: LLM adapter wraps |
| Reflection | `app/ai/reasoning/reflection.py` | Phase 7C: extends |
| Planner | `app/ai/reasoning/planner.py` | Phase 7C: LLM adapter wraps |
| Coordinator | `app/ai/orchestration/coordinator.py` | Phase 7C: intent fix |
| Workflow Engine | `app/ai/orchestration/workflow.py` | Phase 7C: parallel execution |
| Execution Pipeline | `app/ai/runtime/execution.py` | Phase 7C: responder wired |
| LLM Gateway | `app/ai/runtime/llm_gateway.py` | Stable |
| Forecasting (stub) | `app/ai/prediction/forecasting.py` | Phase 7B: XGBoost engine |
| Perception (stubs) | `app/ai/perception/` | Phase 7B: market bridge |
| Agents (stubs) | `app/ai/agents/` | Phase 7C: ReAct executor |

### Infrastructure Kernel (Phase 5.5 — Frozen)

| Component | Status |
|-----------|--------|
| Config system | Frozen |
| Resilience (circuit breaker, retry) | Frozen |
| Security (JWT, RBAC) | Frozen |
| Plugin system | Frozen |
| Event bus | Frozen |
| Task queue | Frozen |
| Health monitor | Frozen |
| Metrics engine | Frozen |

---

## Formula References

All indicator formulas are documented in full at:

→ [`docs/TRADING_ENGINE_BASELINE.md`](../TRADING_ENGINE_BASELINE.md)

Covers: SMA, EMA, RSI, MACD, Bollinger Bands, ATR, Stochastic, VWAP,
Williams %R, CCI, MFI, OBV, Supertrend, Ichimoku, Parabolic SAR,
Fibonacci, Pivot Points (Standard/Camarilla/Woodie), Donchian, Keltner,
all candlestick patterns, BOS, CHoCH, Order Blocks, FVG.

---

## ADR References

| ADR | Decision |
|-----|----------|
| [ADR-001](../adr/ADR-001-brain.md) | Brain as central cognitive controller |
| [ADR-002](../adr/ADR-002-memory.md) | Qdrant + sentence-transformers for LTM |
| [ADR-003](../adr/ADR-003-rag.md) | Hybrid RAG + re-ranking + semantic cache |
| [ADR-004](../adr/ADR-004-agents.md) | ReAct executor + parallel workflow + intent fix |
| [ADR-005](../adr/ADR-005-reasoning.md) | LLM CoT + self-critique loop |
| [ADR-006](../adr/ADR-006-prediction.md) | XGBoostForecastingEngine + TechnicalFeatureExtractor |
| [ADR-007](../adr/ADR-007-market-intelligence.md) | AngelOneMarketPerception bridge |

---

## Research References

| Document | Topic |
|----------|-------|
| [7.1](../research/7.1-memory-research.md) | Memory architecture |
| [7.2](../research/7.2-rag-research.md) | Retrieval-augmented generation |
| [7.3](../research/7.3-agent-research.md) | Agent framework |
| [7.4](../research/7.4-reasoning-research.md) | Reasoning engine |
| [7.5](../research/7.5-prediction-research.md) | Prediction engine |
| [7.6](../research/7.6-market-intelligence.md) | Market intelligence bridge |
| [7.7](../research/7.7-learning-engine.md) | Learning infrastructure |
| [7.8](../research/7.8-xai-research.md) | Explainable AI |
| [7.9](../research/7.9-technology-comparison.md) | Technology selection + Phase 7A-7D plan |

---

## V&V Summary

12 issues found and fixed across 10 files. 0 remaining defects.

| Severity | Count | All Fixed |
|----------|-------|-----------|
| Critical | 2 | ✅ |
| High | 1 | ✅ |
| Medium | 7 | ✅ |
| Low | 2 | ✅ |

Full changelog: [`docs/TRADING_ENGINE_BASELINE.md` § V&V Changelog](../TRADING_ENGINE_BASELINE.md#10-vv-changelog)

---

## Test Baseline

| Suite | Tests | Result |
|-------|-------|--------|
| Phase 3 | included | ✅ |
| Phase 4 | included | ✅ |
| Phase 5 | included | ✅ |
| Phase 5.5 | included | ✅ |
| Phase 6 | included | ✅ |
| **Total** | **1517** | **1517 / 1517 passed** |

---

## Performance Baseline

These are the reference values for the trading engine at this baseline.
Future phases must not degrade these without explicit justification.

| Metric | Value |
|--------|-------|
| TA computation (26 candles) | < 5ms |
| TA computation (200 candles) | < 20ms |
| Regime detection (cached) | < 1ms |
| Regime detection (cold) | < 2s (network fetch) |
| Forecaster prediction (trained model) | < 50ms |
| Paper trade execution | < 100ms (network fetch) |

---

## Known Limitations at This Baseline

| # | Component | Limitation | Target |
|---|-----------|------------|--------|
| 1 | VWAP | Rolling from series start, not reset per session | Phase 8 |
| 2 | BOS/CHoCH | 3-candle swing definition only | Phase 8 |
| 3 | Backtesting | No slippage model | Phase 8 |
| 4 | Backtesting | Long-only | Phase 8 |
| 5 | Ichimoku | Chikou display only, not used in signals | Phase 8 |
| 6 | Forecasting | No independent holdout validation set | Phase 8 |

---

## Modification Policy

Any change to a frozen component requires:

1. A new ADR documenting the reason
2. A V&V entry with before/after formula
3. All 1517 existing tests must continue to pass
4. New tests covering the changed behaviour
5. A new baseline document (`BASELINE_v0.X.Y.md`)

---

## Next Baseline

The next baseline will be created at the completion of Phase 7:

```
docs/architecture_baselines/BASELINE_v0.8.0.md
```

Expected additions:
- Qdrant LTM + sentence-transformers embeddings
- Hybrid RAG + semantic cache
- XGBoostForecastingEngine (real, not mock)
- AngelOneMarketPerception bridge
- ReAct agent executor
- LLM CoT + self-critique
- SHAP explainability
- Decision trace API
