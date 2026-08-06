# JARVIS OS — Repository Inventory

**Version**: v0.6.0  
**Snapshot**: Phase 6 Complete — AI Cognition Runtime  
**Tests**: 1459 / 1459 passing

---

## Statistics

| Category                  | Count |
|---------------------------|-------|
| Production Python files   | 131   |
| Test Python files         | 53    |
| Frontend TS/TSX files     | 42    |
| Documentation files       | 8     |
| Infrastructure files      | 6     |
| Configuration files       | 10+   |
| **Total tracked files**   | ~280  |

---

## Backend

```
backend/
├── app/
│   ├── ai/                              ← AI Cognition Runtime (Phase 6)
│   │   ├── __init__.py
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── analyst.py               ← AnalystAgent
│   │   │   ├── base.py                  ← BaseAgent ABC
│   │   │   ├── planner.py               ← PlannerAgent
│   │   │   ├── researcher.py            ← ResearcherAgent
│   │   │   └── trader.py                ← TraderAgent + TradeSignal
│   │   ├── brain/
│   │   │   └── brain.py                 ← Brain controller
│   │   ├── memory/
│   │   │   ├── __init__.py              ← MemoryPipelineProvider
│   │   │   ├── embeddings.py            ← EmbeddingService ABC + SimpleEmbeddingService
│   │   │   ├── long_term.py             ← LongTermMemory ABC + InMemoryLongTermMemory
│   │   │   └── short_term.py            ← ShortTermMemory + MemoryEntry
│   │   ├── orchestration/
│   │   │   ├── coordinator.py           ← Coordinator
│   │   │   └── workflow.py              ← WorkflowEngine (DAG)
│   │   ├── perception/
│   │   │   ├── __init__.py
│   │   │   ├── market.py                ← MarketPerception ABC + InMemory stub
│   │   │   ├── news.py                  ← NewsPerception ABC + InMemory stub
│   │   │   └── sentiment.py             ← SentimentPerception ABC + InMemory stub
│   │   ├── prediction/
│   │   │   ├── __init__.py
│   │   │   ├── confidence.py            ← ConfidenceScorer
│   │   │   ├── feature_store.py         ← FeatureStore + FeatureVector
│   │   │   └── forecasting.py           ← ForecastingEngine ABC + MockForecastingEngine
│   │   ├── prompts/
│   │   │   ├── __init__.py
│   │   │   ├── system.py                ← SystemPromptBuilder + PipelineResponderAdapter
│   │   │   └── templates.py             ← PromptTemplate + TemplateRegistry (6 built-ins)
│   │   ├── reasoning/
│   │   │   ├── __init__.py
│   │   │   ├── chain.py                 ← ChainOfThought + PipelineReasonerAdapter
│   │   │   ├── planner.py               ← ReasoningPlanner + PipelinePlannerAdapter
│   │   │   └── reflection.py            ← Reflection + VerificationResult
│   │   ├── runtime/
│   │   │   ├── __init__.py              ← AIRuntime facade
│   │   │   ├── context.py               ← PipelineContext
│   │   │   ├── execution.py             ← ExecutionEngine
│   │   │   └── llm_gateway.py           ← LLMGateway
│   │   ├── skills/
│   │   │   └── __init__.py              ← BaseSkill + SkillRegistry
│   │   └── tools/
│   │       ├── __init__.py
│   │       └── registry.py              ← BaseTool + AIToolRegistry (RBAC + timeout)
│   │
│   ├── agents/                          ← Legacy agent layer
│   │   ├── __init__.py
│   │   ├── coordinator.py
│   │   └── scientific.py
│   │
│   ├── api/                             ← FastAPI routes
│   │   ├── __init__.py
│   │   ├── ai_analyst.py
│   │   ├── alert_engine.py
│   │   ├── angel_feed.py
│   │   ├── auto_trader.py
│   │   ├── backtesting.py
│   │   ├── budget_advisor.py
│   │   ├── data_quality.py
│   │   ├── forecaster.py
│   │   ├── market_intelligence.py
│   │   ├── market_regime.py
│   │   ├── model_validator.py
│   │   ├── mtf_analysis.py
│   │   ├── paper_trading.py
│   │   ├── routes.py
│   │   ├── stock_data.py
│   │   ├── stock_fetcher.py
│   │   ├── stock_universe.py
│   │   └── technical_analysis.py
│   │
│   ├── config/                          ← Configuration Kernel (Phase 5)
│   │   ├── settings/
│   │   │   ├── __init__.py
│   │   │   ├── ai.py
│   │   │   ├── app.py
│   │   │   ├── broker.py
│   │   │   ├── cache.py
│   │   │   ├── logging.py
│   │   │   ├── market.py
│   │   │   ├── provider.py
│   │   │   └── risk.py
│   │   ├── __init__.py
│   │   ├── environment.py
│   │   ├── exceptions.py
│   │   └── retry_policy.py
│   │
│   ├── core/                            ← Infrastructure Kernel (Phase 5.5)
│   │   ├── di/container.py              ← DI container
│   │   ├── events/bus.py                ← Event bus
│   │   ├── health/monitor.py            ← Health monitor
│   │   ├── lifecycle/manager.py         ← Lifecycle manager
│   │   ├── metrics/engine.py            ← Metrics engine
│   │   ├── plugins/loader.py            ← Plugin loader
│   │   ├── queue/task_queue.py          ← Task queue
│   │   ├── scheduler/scheduler.py       ← Scheduler
│   │   ├── service_registry/registry.py ← Service registry
│   │   ├── workers/pool.py              ← Worker pool
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── identity.py
│   │   ├── learning.py
│   │   ├── llm.py
│   │   ├── orchestrator.py
│   │   └── personality.py
│   │
│   ├── market_data/                     ← Market data providers
│   │   ├── providers/
│   │   │   ├── angel_auth.py
│   │   │   ├── angel_one.py
│   │   │   ├── base.py
│   │   │   ├── manager.py
│   │   │   └── yahoo.py
│   │   ├── cache.py
│   │   ├── instruments.py
│   │   ├── service.py
│   │   └── validator.py
│   │
│   ├── memory/                          ← Legacy memory layer
│   │   ├── manager.py
│   │   └── vector_store.py
│   │
│   ├── models/database.py
│   ├── plugins/manager.py
│   ├── reasoning/engine.py
│   ├── resilience/retry.py
│   ├── security/manager.py
│   ├── tools/
│   │   ├── code_generator.py
│   │   ├── live_data.py
│   │   ├── registry.py
│   │   └── web_search.py
│   ├── voice/interface.py
│   ├── __init__.py
│   └── main.py
│
├── models/                              ← Trained XGBoost models
│   ├── ALLCARGO_h6_xgb.pkl + .meta
│   ├── AXISBANK_h3_xgb.pkl + .meta
│   ├── BAJFINANCE_h3_xgb.pkl + .meta
│   ├── DRREDDY_h3_xgb.pkl + .meta
│   ├── HCLTECH_h3_xgb.pkl + .meta
│   ├── HDFCLIFE_h3_xgb.pkl + .meta
│   ├── HINDALCO_h3_xgb.pkl + .meta
│   ├── ICICIBANK_h3_xgb.pkl + .meta
│   ├── INFY_h3_xgb.pkl + .meta
│   ├── JSWSTEEL_h3_xgb.pkl + .meta
│   ├── KOTAKBANK_h3_xgb.pkl + .meta
│   ├── RELIANCE_h6_xgb.pkl + .meta
│   └── SHILPAMED_h6_xgb.pkl + .meta
│
├── tests/
│   ├── phase3/   (9 files)              ← Validation tests
│   ├── phase4/   (4 files)              ← Cleanup tests
│   ├── phase5/   (13 files)             ← Config kernel tests
│   ├── phase5_5/ (6 files)              ← Infrastructure kernel tests
│   └── phase6/   (16 files)             ← AI runtime tests (1459 tests)
│       ├── test_6a_brain.py
│       ├── test_6a_context.py
│       ├── test_6a_coordinator.py
│       ├── test_6a_execution.py
│       ├── test_6a_llm_gateway.py
│       ├── test_6a_runtime.py
│       ├── test_6a_workflow.py
│       ├── test_6b_memory.py            ← 77 tests
│       ├── test_6c_reasoning.py         ← 80 tests
│       ├── test_6d_agents_base.py       ← 28 tests
│       ├── test_6d_agents_domain.py     ← 40 tests
│       ├── test_6d_skills.py            ← 22 tests
│       ├── test_6d_tools.py             ← 22 tests
│       ├── test_6d_perception.py        ← 36 tests
│       ├── test_6d_prediction.py        ← 30 tests
│       └── test_6d_integration.py       ← 24 tests
│
├── .env.example                         ← Template — no secrets
└── requirements.txt
```

---

## Frontend

```
frontend/
├── src/
│   ├── app/
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   ├── not-found.tsx
│   │   └── page.tsx
│   ├── components/                      ← 37 React components
│   │   ├── AgentCards.tsx
│   │   ├── AgentsPanel.tsx
│   │   ├── AIDiscoveryPage.tsx
│   │   ├── BacktestPage.tsx
│   │   ├── BottomNav.tsx
│   │   ├── BottomRow.tsx
│   │   ├── BudgetAdvisorPage.tsx
│   │   ├── CalendarPage.tsx
│   │   ├── CenterColumn.tsx
│   │   ├── ChatInterface.tsx
│   │   ├── ConnectionsPanel.tsx
│   │   ├── Header.tsx
│   │   ├── HolographicCore.tsx
│   │   ├── HolographicModal.tsx
│   │   ├── HudPanelManager.tsx
│   │   ├── IntradayAssistantPage.tsx
│   │   ├── JarvisOverlay.tsx
│   │   ├── LeftPanel.tsx
│   │   ├── LLMStatus.tsx
│   │   ├── MarketDashboardPage.tsx
│   │   ├── NewsPage.tsx
│   │   ├── Notifications.tsx
│   │   ├── NotificationToasts.tsx
│   │   ├── PaperTradingPage.tsx
│   │   ├── ParticleBackground.tsx
│   │   ├── PortfolioPage.tsx
│   │   ├── QuickTradeModal.tsx
│   │   ├── RightPanel.tsx
│   │   ├── SettingsPage.tsx
│   │   ├── Sidebar.tsx
│   │   ├── StocksPage.tsx
│   │   ├── StocksPanel.tsx
│   │   ├── SystemMonitor.tsx
│   │   ├── TaskPanel.tsx
│   │   ├── TopPicksPage.tsx
│   │   ├── VoiceBar.tsx
│   │   └── WatchlistPage.tsx
│   ├── store/
│   │   └── jarvisStore.ts               ← Zustand global state
│   └── lib/
│       └── voiceRouter.ts
├── static/
│   ├── favicon.ico
│   └── index.html
├── package.json
├── package-lock.json
├── next.config.js
├── tailwind.config.js
├── postcss.config.js
└── tsconfig.json
```

---

## Documentation

```
docs/
├── ai-runtime-architecture.md           ← AI Runtime design doc
├── plugin-sdk.md                        ← Plugin development guide
└── scientific-intelligence.md           ← Scientific intelligence design

README.md                                ← Project overview + quick start
CHANGELOG.md                             ← Version history
ROADMAP.md                               ← Phase 7+ plans
ARCHITECTURE.md                          ← Full system architecture
PROJECT_STATUS.md                        ← Current status + progress board
REPOSITORY_INVENTORY.md                  ← This file
```

---

## Infrastructure

```
infrastructure/
├── docker/
│   ├── docker-compose.yml
│   ├── Dockerfile.backend
│   └── Dockerfile.frontend
└── k8s/
    └── backend-deployment.yaml

.github/
└── workflows/
    └── ci.yml
```

---

## Plugins

```
plugins/
└── example_plugin/
    ├── main.py
    └── manifest.json
```

---

## Root Configuration

```
.gitignore                               ← Comprehensive ignore rules
pytest.ini                               ← Test configuration
instruments_cache.json                   ← Nifty 50 instrument cache
```

---

## What Is NOT in This Repository

The following are intentionally excluded (see `.gitignore`):

| Excluded                  | Reason                              |
|---------------------------|-------------------------------------|
| `.env`                    | Contains API keys and secrets       |
| `backend/logs/`           | Runtime log files                   |
| `__pycache__/`            | Python bytecode cache               |
| `.pytest_cache/`          | Test runner cache                   |
| `node_modules/`           | npm packages (install from package.json) |
| `.next/`                  | Next.js build output                |
| `*.db`, `*.sqlite`        | Local database files                |
| `venv/`, `.venv/`         | Python virtual environment          |
| `*.log`                   | Log files                           |

---

## Verification Checklist

A fresh developer can:

- [x] `git clone https://github.com/frinod/Jarvis.git`
- [x] `cd backend && pip install -r requirements.txt`
- [x] `cp .env.example .env` and fill in one AI provider key
- [x] `uvicorn app.main:app --reload` — backend starts
- [x] `cd frontend && npm install && npm run dev` — frontend starts
- [x] `python -m pytest tests/ -q` — 1459 tests pass
- [x] Continue Phase 7 development without any missing files
