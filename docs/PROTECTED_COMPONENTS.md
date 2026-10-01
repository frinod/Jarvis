# JARVIS OS — Protected Components Registry

**Created:** Phase A — Advanced JARVIS Implementation  
**Baseline test count:** 2009 passed, 0 failed, 0 skipped (204.67s)  
**Rule:** Protected-by-default. Changes require justification, test plan, and explicit approval.

---

## 1. Protected Backend — Market Data Pipeline

| File | Purpose | Protection reason |
|---|---|---|
| `backend/app/market_data/service.py` | fetch_candles, snapshot cache, explicit_range flag | Core data pipeline — all market features depend on it |
| `backend/app/market_data/cache.py` | get_snapshot/set_snapshot, bucketed TTL key | Rate-limit fix — deduplicates Angel One calls |
| `backend/app/market_data/validator.py` | nse_market_open(), check_candle_freshness(), FreshnessResult | Authoritative market-session and freshness gate |
| `backend/app/market_data/providers/angel_one.py` | _CHUNK_SEM semaphore, exponential backoff | Rate-limit fix — serializes concurrent chunk requests |
| `backend/app/market_data/providers/yahoo.py` | Yahoo Finance fallback provider | Fallback when Angel One unavailable |
| `backend/app/market_data/providers/base.py` | Candle, Quote dataclasses | Shared data contracts |
| `backend/app/market_data/providers/manager.py` | Provider selection logic | Routes between Angel One and Yahoo |
| `backend/app/market_data/instruments.py` | NSE instrument token lookup | Required for Angel One symbol resolution |

---

## 2. Protected Backend — Analysis & Prediction

| File | Purpose | Protection reason |
|---|---|---|
| `backend/app/api/technical_analysis.py` | RSI, MACD, EMA, BB, Supertrend, Ichimoku, Fibonacci, OBV, MFI, ATR, VWAP, S/R, BOS/CHoCH, FVG, Order Blocks | Single source of truth for all TA — must not be duplicated |
| `backend/app/api/forecaster.py` | XGBoost training, prediction, WFV, freshness gate, regime filter, MTF confirmation, calibrated confidence | Core prediction engine — 50+ trained models depend on this |
| `backend/app/api/ai_analyst.py` | LLM-powered buy/sell/hold analysis | AI analysis layer over TA |
| `backend/app/api/market_intelligence.py` | Movers, heatmap, AI discovery, depth, news, intraday assistant | Market intelligence aggregation |
| `backend/app/api/market_regime.py` | NIFTY regime classification (strong_bull → panic), apply_regime_filter | Regime-aware signal filtering |
| `backend/app/api/mtf_analysis.py` | 1h/4h/1d multi-timeframe confluence | MTF confirmation layer |
| `backend/app/api/model_validator.py` | record_prediction, resolve_prediction, get_pending_predictions, walk_forward_test, get_calibrated_accuracy | Prediction tracking and WFV accuracy |
| `backend/app/api/stock_data.py` | Fundamentals, financials, shareholding, peers | Fundamental data layer |
| `backend/app/api/stock_fetcher.py` | get_all_stocks, fetch_quote, NIFTY50 batch fetch | Stock list and quote fetching |
| `backend/app/api/stock_universe.py` | NIFTY50_SYMBOLS, NAME_MAP, SECTOR_MAP, UNIVERSE_MAP | Symbol/name/sector registry |
| `backend/app/api/data_quality.py` | clean_candles, quality scoring | Data quality gate before analysis |

---

## 3. Protected Backend — Trading

| File | Purpose | Protection reason |
|---|---|---|
| `backend/app/api/paper_trading.py` | Portfolio, Trade, Position, execute_trade, ai_auto_trade, confirm_ai_trade, get_ai_self_evaluation, resolve_pending_predictions | Paper trading engine with real brokerage charges |
| `backend/app/api/auto_trader.py` | Autonomous trading loop, self-healing, cfg patches | Autonomous trading system |
| `backend/app/api/backtesting.py` | Strategy backtesting, compare_strategies | Historical strategy validation |
| `backend/app/api/alert_engine.py` | set_alert, price polling, Angel One tick priority | Real-time price alert system |
| `backend/app/api/budget_advisor.py` | Budget-based stock recommendations | Budget-aware recommendation engine |
| `backend/jarvis_paper_trading.json` | Persisted portfolio state | Live portfolio data — never overwrite |

---

## 4. Protected Backend — Core AI

| File | Purpose | Protection reason |
|---|---|---|
| `backend/app/core/orchestrator.py` | JarvisOrchestrator, _get_live_context, _fetch_stock_context, process_message, process_stream | Main AI brain — all chat routes go through here |
| `backend/app/ai/brain/brain.py` | Brain, Goal, GoalStatus, DecisionRecord, ReflectionResult, BrainCapabilities | Cognitive controller |
| `backend/app/ai/agents/analyst.py` | AnalystAgent — technical analysis + RAG + collaboration | Market analysis agent |
| `backend/app/ai/agents/trader.py` | TraderAgent — XGBoost signal generation + collaboration bus | Trade signal agent |
| `backend/app/ai/agents/planner.py` | PlannerAgent | Planning agent |
| `backend/app/ai/agents/researcher.py` | ResearcherAgent | Research agent |
| `backend/app/ai/agents/base.py` | BaseAgent, AgentPlan, AgentResult, VerificationResult | Agent contracts |
| `backend/app/ai/agents/collaboration.py` | AgentCollaborationBus, AgentMessage, CollaborationContext | Inter-agent communication |
| `backend/app/ai/orchestration/coordinator.py` | AgentCoordinator, AgentRegistry, CapabilityMatchPolicy, CoordinatorAgentSelector | Agent selection and routing |
| `backend/app/ai/orchestration/workflow.py` | Workflow execution | Workflow management |
| `backend/app/ai/runtime/context.py` | ExecutionContext | Pipeline context |
| `backend/app/ai/runtime/execution.py` | ExecutionEngine | Pipeline execution |
| `backend/app/ai/runtime/llm_gateway.py` | LLMGateway, LLMRequest | LLM routing with retry/fallback |
| `backend/app/ai/memory/` | Short-term, long-term, Qdrant, embeddings, sentence transformers | Memory subsystem |
| `backend/app/ai/rag/` | context_builder, retriever, reranker, semantic_cache | RAG pipeline |
| `backend/app/ai/reasoning/` | chain, decision_tree, planner, reasoning_log, reflection | Reasoning engine |
| `backend/app/ai/xai/` | shap_explainer, explanation_formatter, xai_cache | Explainability layer |
| `backend/app/ai/learning/` | feedback_collector, model_evaluator, model_registry, retraining_trigger | Learning engine |
| `backend/app/ai/prediction/` | forecasting.py (ForecastResult), feature_store, confidence | Prediction abstractions |
| `backend/app/ai/perception/` | market.py, news.py, sentiment.py | Market perception layer |
| `backend/app/ai/prompts/` | system.py, templates.py | LLM prompt templates |
| `backend/app/core/llm.py` | LLMRouter, LLMMessage, LLMResponse | LLM provider routing (Groq/Gemini/DeepSeek) |
| `backend/app/core/personality.py` | PersonalityEngine, SYSTEM_PROMPT | JARVIS personality and tone |
| `backend/app/core/identity.py` | JarvisCore, FocusState | JARVIS identity and state |

---

## 5. Protected Backend — Infrastructure

| File | Purpose |
|---|---|
| `backend/app/api/routes.py` | All existing API routes — new routes may be ADDED, existing routes must not be modified |
| `backend/app/main.py` | FastAPI app startup, lifespan, orchestrator init |
| `backend/app/config/` | All settings (ai, app, broker, cache, logging, market, provider, risk) |
| `backend/app/core/` | DI container, event bus, health monitor, lifecycle, metrics, plugins, queue, scheduler, service registry, workers |
| `backend/app/resilience/retry.py` | Retry policy |
| `backend/app/security/manager.py` | Security and approval system |
| `backend/app/plugins/manager.py` | Plugin loader |
| `backend/app/tools/` | Tool registry, web_search, live_data, code_generator |
| `backend/app/memory/` | Memory manager, vector store |
| `backend/app/reasoning/engine.py` | Reasoning engine |
| `backend/app/agents/coordinator.py` | Agent coordinator (legacy layer) |
| `backend/app/voice/interface.py` | Backend voice interface stubs |
| `backend/app/models/database.py` | Database models |
| `backend/.env` | Environment variables — never commit secrets |
| `backend/requirements.txt` | Python dependencies — no new deps without justification |

---

## 6. Protected XGBoost Models

All files in `backend/models/` are protected:

- 50+ trained `.pkl` model files (RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, AXISBANK, etc.)
- 50+ `.meta` timestamp files
- `backend/models/wfv/` — walk-forward validation results

**Rule:** Never delete, overwrite, or retrain models without explicit approval. Models represent significant compute investment.

---

## 7. Protected Frontend — Market UI Pages

| File | Purpose |
|---|---|
| `frontend/src/components/MarketDashboardPage.tsx` | Market overview dashboard |
| `frontend/src/components/StocksPage.tsx` | Stock analysis page |
| `frontend/src/components/PaperTradingPage.tsx` | Paper trading interface |
| `frontend/src/components/BacktestPage.tsx` | Backtesting lab |
| `frontend/src/components/IntradayAssistantPage.tsx` | Intraday signals |
| `frontend/src/components/TopPicksPage.tsx` | AI top picks |
| `frontend/src/components/AIDiscoveryPage.tsx` | AI discovery |
| `frontend/src/components/WatchlistPage.tsx` | Watchlist |
| `frontend/src/components/PortfolioPage.tsx` | Portfolio tracker |
| `frontend/src/components/NewsPage.tsx` | Market news |
| `frontend/src/components/CalendarPage.tsx` | Economic calendar |
| `frontend/src/components/BudgetAdvisorPage.tsx` | Budget advisor |
| `frontend/src/components/SettingsPage.tsx` | Settings |
| All other existing page components | — |

---

## 8. Protected Tests

All test files in `backend/tests/` are protected:

| Directory | Phase | Count (approx) |
|---|---|---|
| `backend/tests/phase3/` | Core AI, memory, reasoning | ~300 tests |
| `backend/tests/phase4/` | Orchestrator, LLM, agents | ~350 tests |
| `backend/tests/phase5/` | Market data, TA, forecasting | ~400 tests |
| `backend/tests/phase5_5/` | Data quality, validator | ~200 tests |
| `backend/tests/phase6/` | Paper trading, backtesting, alerts | ~350 tests |
| `backend/tests/phase7/` | WFV, prediction resolution, AI runtime | ~400 tests |

**Baseline:** 2009 passed, 0 failed, 0 skipped (run: 2025-09-11, 204.67s)

**Rule:** No new code may be merged if it causes any previously-passing test to fail.

---

## 9. Capability Registry — Verified Endpoints

All endpoints below were verified against actual source code:

| Tool | Endpoint | Method | Key response fields |
|---|---|---|---|
| StockAnalysisTool | `/api/stocks/analyze/{symbol}` | GET | `technical`, `ai_analysis`, `interval_used`, `candles_used` |
| ForecastTool | `/api/stocks/forecast/{symbol}` | GET | `forecast.direction/confidence/prob_*`, `regime`, `mtf`, `validation.wfv_accuracy/wfv_useful`, `data_quality` |
| MTFTool | `/api/market/mtf/{symbol}` | GET | `timeframes.1h/4h/1d`, `confluence.level/score/htf_signal/recommendation` |
| RegimeTool | `/api/market/regime` | GET | `regime`, `label`, `confidence`, `allow_longs`, `allow_shorts`, `reduce_size`, `metrics`, `recommendation` |
| IntradayTool | `/api/market/intraday/{symbol}` | GET | `signal`, `regime_adjusted`, `entry`, `stop_loss`, `target1/2`, `momentum`, `data_quality` |
| ConfluenceTool | `/api/market/confluence/{symbol}` | GET | `confluence[]`, `verdict`, `buy_count`, `sell_count` |
| MoversTool | `/api/market/movers` | GET | `gainers`, `losers`, `most_active`, `volume_leaders`, `advancing`, `declining` |
| NewsTool | `/api/market/news` | GET | `news[].title/source/sentiment/impact/published` |
| TopPicksTool | `/api/market/top-picks` | GET | `intraday[]`, `swing[]`, `longterm[]`, `summary.market_mood` |
| ModelAccuracyTool | `/api/market/model-accuracy` | GET | `summaries[].symbol/signal/accuracy/sample_size` |
| PortfolioTool | `/api/paper/portfolio/{pid}` | GET | `cash`, `total_value`, `positions{}`, `realised_pnl`, `total_return_pct` |
| PaperTradeTool | `/api/paper/ai-trade/{pid}` | POST | `status`, `proposal.confirmation_id/signal/confidence/stop_loss/target1/wfv_useful` |
| PriceAlertTool | `/api/alerts/set` | POST | `status`, `symbol`, `above`, `below` |
| GeneralAITool | `/api/ws/chat` (WS) | WS | streaming tokens + `status` |
| MarketSessionTool | `validator.nse_market_open()` | Internal | `bool` — authoritative NSE session state |
| FreshnessTool | `validator.check_candle_freshness()` | Internal | `FreshnessResult.status/age_minutes/is_fresh` |

**Known caveats (verified):**
- ForecastTool returns `{"error": "DATA_STALE"}` during market hours if candles >30 min old — JARVIS must handle gracefully
- PaperTradeTool returns `{"status": "no_trade"}` when confidence <55% or direction FLAT — not an error
- TopPicksTool scans 60 stocks with XGBoost — takes 20-30s — JARVIS must warn user
- Market depth endpoint returns simulated data — must be labeled as such
- PortfolioTool requires active portfolio ID from store

---

## 10. Market Session Authority

| Responsibility | Frontend `marketSession.ts` | Backend `validator.py` |
|---|---|---|
| Display session state to user | ✅ UX only | — |
| Block UI interactions when closed | ✅ UX only | — |
| Show "market opens in X hours" | ✅ UX only | — |
| Authoritative gate for live data | ❌ | ✅ `nse_market_open()` |
| Freshness validation on candles | ❌ | ✅ `check_candle_freshness()` |
| DATA_STALE error in forecast | ❌ | ✅ already in `forecaster.py` |
| Holiday enforcement | Display only | ✅ authoritative |

---

## 11. New Files Being Added (Phase B+)

These files are NEW — they do not modify any protected component:

| File | Phase | Purpose |
|---|---|---|
| `frontend/src/lib/vad.ts` | B1 | Energy-based VAD (Web Audio) |
| `frontend/src/lib/assembler.ts` | B2 | Utterance assembler |
| `frontend/src/lib/tts.ts` | B3 | TTS manager (browser + optional Kokoro) |
| `frontend/src/lib/wakeWord.ts` | B4 | "Hey Jarvis" wake word |
| `frontend/src/lib/marketSession.ts` | C1 | NSE session state (UX only) |
| `frontend/src/lib/intentRouter.ts` | C2 | Intent classifier + tool planner |
| `frontend/src/lib/capabilityTools.ts` | C3 | 15 tool wrappers → existing endpoints |
| `frontend/src/components/JarvisBoot.tsx` | B7 | Boot sequence animation |
| `frontend/src/components/JarvisHud.tsx` | D1 | Enhanced HUD |
| `frontend/src/components/MarketVoicePanel.tsx` | D2 | Voice-triggered market result display |
| `backend/app/api/jarvis_intent.py` | C4 | Thin LLM-assisted intent classifier |
| `docs/PROTECTED_COMPONENTS.md` | A1 | This file |

**Modified files (extensions only, no removals):**

| File | Phase | Change |
|---|---|---|
| `frontend/src/store/jarvisStore.ts` | B5 | Add `phase`, `marketSession`, `voiceIntent`, `activeToolName` fields |
| `frontend/src/components/VoiceBar.tsx` | B6 | Wire VAD + assembler + wake-word + echo guard |
| `frontend/src/lib/voiceRouter.ts` | C2 | Extend INTENTS with market-aware tool-call patterns |
| `backend/app/api/routes.py` | C4 | Add `POST /api/jarvis/intent` and `POST /api/jarvis/plan` routes only |
