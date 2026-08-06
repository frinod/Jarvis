# JARVIS OS — Architecture Document

**Version**: v0.6.0  
**Status**: Phase 6 Complete — AI Cognition Runtime

---

## 1. Overview

JARVIS OS is structured as a layered system:

```
┌─────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                    │
│         Next.js 13 + React 18 + Tailwind CSS            │
│         Iron Man HUD  │  Chat  │  Voice  │  Trading     │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / WebSocket
┌────────────────────────▼────────────────────────────────┐
│                      API LAYER                           │
│              FastAPI routes + WebSocket                  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│               AI COGNITION RUNTIME                       │
│  Brain ──► Coordinator ──► ExecutionEngine               │
│  Memory │ Reasoning │ Agents │ Perception │ Prediction   │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│               INFRASTRUCTURE KERNEL                      │
│  DI Container │ Event Bus │ Lifecycle │ Service Registry │
│  Plugin Loader │ Task Queue │ Scheduler │ Worker Pool    │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│               CONFIGURATION KERNEL                       │
│  AppSettings │ AISettings │ MarketSettings │ RiskSettings│
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                    DATA LAYER                            │
│  SQLite/PostgreSQL │ Yahoo Finance │ Angel One │ XGBoost │
└─────────────────────────────────────────────────────────┘
```

---

## 2. AI Cognition Runtime (`app/ai/`)

### 2.1 Runtime Core

```
AIRuntime (facade)
    │
    ├── Brain                    ← top-level cognitive controller
    │       └── routes to Coordinator
    │
    ├── Coordinator              ← orchestrates multi-step workflows
    │       └── WorkflowEngine  ← DAG execution (WorkflowNode.depends_on)
    │
    └── ExecutionEngine          ← step-by-step pipeline execution
            └── PipelineContext  ← shared mutable context
```

**Key design decisions:**
- `PipelineContext` is the single shared state object passed through all pipeline steps
- `WorkflowNode.depends_on` already supports DAG — Phase 7 parallel execution = replace sequential loop with `asyncio.gather()`
- `CapabilityMatchPolicy` reads intent from `goal.metadata.get("intent_type", "")` only

### 2.2 Memory System

```
MemoryPipelineProvider
    │
    ├── ShortTermMemory          ← deque ring buffer, maxlen=50
    │       └── MemoryEntry      ← id, content, role, importance, timestamp, embedding
    │
    ├── LongTermMemory (ABC)     ← importance_threshold=0.6
    │       └── InMemoryLongTermMemory  ← dict-backed (Phase 7: Qdrant)
    │
    └── EmbeddingService (ABC)   ← encode(), similarity(), top_k()
            └── SimpleEmbeddingService  ← bag-of-words cosine (Phase 7: SentenceTransformer)
```

**Deduplication**: by `MemoryEntry.id`. Graceful degradation when LTM/embeddings absent.

### 2.3 Reasoning Engine

```
ReasoningPlanner          ← intent detection (question/task/analysis/general)
    └── PipelinePlannerAdapter  ← sets ctx.active_goal, ctx.intent_type

ChainOfThought            ← 5-step chain from context evidence
    └── PipelineReasonerAdapter

Reflection                ← evaluates chain: length, confidence, stability, evidence
    └── PipelineVerifierAdapter

TemplateRegistry          ← 6 built-in templates
SystemPromptBuilder       ← assembles [system, history, memory, thought_chain, user_input]
    └── PipelineResponderAdapter  ← calls LLMGateway, writes ctx.response
```

### 2.4 Agent Framework

```
BaseAgent (ABC)
    ├── can_handle(context) → bool
    ├── plan(context) → AgentPlan
    ├── execute(plan, context) → AgentResult
    ├── verify(result, context) → VerificationResult
    ├── confidence(context) → float
    ├── explain(result) → str
    └── learn(result, context) → None

Domain agents:
    ├── AnalystAgent    ← analysis / technical_analysis / market_context
    ├── ResearcherAgent ← research / news / fundamentals / question
    ├── TraderAgent     ← trading / signal_generation / execution
    │       └── TradeSignal stored in AgentResult.metadata["trade_signal"]
    └── PlannerAgent    ← planning / task / decomposition
```

**Domain agnosticism rule**: No trading/stock/RSI/MACD fields as first-class attributes on any agent or result. Domain data belongs in `metadata: Dict[str, Any]` only.

### 2.5 Perception + Prediction

```
Perception (ABCs + in-memory stubs):
    ├── MarketPerception   → PerceptionBundle
    ├── NewsPerception     → List[NewsItem]
    └── SentimentPerception → SentimentScore

Prediction:
    ├── FeatureStore       ← numeric extraction from bundles → FeatureVector
    ├── ForecastingEngine  ← ABC + MockForecastingEngine (Phase 7: XGBoost)
    └── ConfidenceScorer   ← prediction(50%) + TA signal(30%) + sentiment(20%)
```

---

## 3. Infrastructure Kernel (`app/core/`)

| Module             | Package                    | Responsibility                        |
|--------------------|----------------------------|---------------------------------------|
| DI Container       | `core/di/`                 | Dependency injection, service wiring  |
| Event Bus          | `core/events/`             | Pub/sub event routing                 |
| Lifecycle Manager  | `core/lifecycle/`          | Start/stop/health of services         |
| Service Registry   | `core/service_registry/`   | Named service lookup                  |
| Plugin Loader      | `core/plugins/`            | Dynamic plugin discovery + loading    |
| Task Queue         | `core/queue/`              | Async task queuing                    |
| Scheduler          | `core/scheduler/`          | Cron-style job scheduling             |
| Worker Pool        | `core/workers/`            | Thread/async worker management        |
| Health Monitor     | `core/health/`             | Service health aggregation            |
| Metrics Engine     | `core/metrics/`            | Counter/gauge/histogram collection    |

**Kernel freeze**: No new packages under `app/core/`, `app/config/`, `app/resilience/` without Architecture Change Proposal (ACP).

---

## 4. Configuration Kernel (`app/config/`)

All settings are typed Pydantic models loaded from environment variables.

| Settings class    | File                      | Key fields                              |
|-------------------|---------------------------|-----------------------------------------|
| `AppSettings`     | `settings/app.py`         | debug, host, port, cors_origins         |
| `AISettings`      | `settings/ai.py`          | provider, model, temperature, max_tokens|
| `MarketSettings`  | `settings/market.py`      | universe, price_cap, budget_per_trade   |
| `RiskSettings`    | `settings/risk.py`        | max_drawdown, position_size, stop_loss  |
| `BrokerSettings`  | `settings/broker.py`      | angel_one credentials                   |
| `CacheSettings`   | `settings/cache.py`       | redis_url, ttl                          |
| `LoggingSettings` | `settings/logging.py`     | level, format, rotation                 |

---

## 5. Market Data Layer (`app/market_data/`)

```
MarketDataService
    │
    ├── ProviderManager
    │       ├── YahooFinanceProvider   ← OHLCV candles (primary)
    │       └── AngelOneProvider       ← live tick feed (optional)
    │
    ├── InstrumentsCache               ← Nifty 50 symbol list
    ├── MarketDataCache                ← TTL-based OHLCV cache
    └── MarketDataValidator            ← schema + range validation
```

---

## 6. API Layer (`app/api/`)

All endpoints are FastAPI routers mounted in `app/main.py`.

| Router                  | Prefix              | Key endpoints                          |
|-------------------------|---------------------|----------------------------------------|
| `routes.py`             | `/api`              | `/chat`, `/ws/chat`                    |
| `paper_trading.py`      | `/api/paper`        | `/autotest/start`, `/status`           |
| `auto_trader.py`        | `/api/trader`       | `/start`, `/stop`, `/status`           |
| `forecaster.py`         | `/api/forecast`     | `/{symbol}`                            |
| `technical_analysis.py` | `/api/ta`           | `/{symbol}`                            |
| `stock_data.py`         | `/api/stocks`       | `/{symbol}`, `/universe`               |
| `backtesting.py`        | `/api/backtest`     | `/run`                                 |

---

## 7. Security

- JWT authentication via `python-jose`
- `SecurityManager` (`app/security/`) — token issue/verify/revoke
- `AIToolRegistry` — RBAC `allowed_roles` per tool, enforced at call time
- No secrets in source code — all credentials via `.env`
- `.env` is in `.gitignore`

---

## 8. Testing Architecture

```
backend/tests/
    ├── phase3/    ← module consistency, provider validation, performance
    ├── phase4/    ← orchestrator, dead code
    ├── phase5/    ← all settings classes, environment, retry policy
    ├── phase5_5/  ← DI, event bus, lifecycle, service registry, plugins
    └── phase6/    ← AI runtime (16 files, 1459 tests)
```

**Test conventions:**
- One test file per component (SRP)
- `TestDomainAgnosticism` class mandatory in every Phase 6 file
- No file exceeds ~300 lines
- All tests are pure unit tests — no network, no filesystem, no DB

---

## 9. Technical Debt

| Item                                    | Priority | Phase  |
|-----------------------------------------|----------|--------|
| `InMemoryLongTermMemory` → Qdrant       | High     | 7      |
| `SimpleEmbeddingService` → SentenceTransformer | High | 7   |
| Sequential workflow → `asyncio.gather()`| Medium   | 7      |
| `MockForecastingEngine` → real XGBoost  | High     | 7      |
| `InMemoryMarketPerception` → real feed  | High     | 7      |
| Python 3.7.9 → 3.11+                   | Medium   | 8      |
| SQLite → PostgreSQL (production)        | Medium   | 8      |
| JWT → OAuth2 / API key rotation         | Medium   | 8      |

---

## 10. Extension Points

### Adding a new Agent
1. Subclass `BaseAgent` in `app/ai/agents/`
2. Implement all 7 abstract methods
3. Register with `AgentRegistry` (Phase 7)
4. Domain data goes in `AgentResult.metadata` — never as first-class fields

### Adding a new Skill
1. Subclass `BaseSkill` in `app/ai/skills/`
2. Implement `execute(input_data) → SkillResult`
3. Register: `registry.register(MySkill())`

### Adding a new Tool
1. Subclass `BaseTool` in `app/ai/tools/`
2. Implement `async execute(params) → ToolResult`
3. Register: `registry.register(tool, allowed_roles=["analyst"])`

### Adding a new LLM Provider
1. Add provider key to `.env.example`
2. Add routing logic in `LLMGateway`
3. Add settings in `AISettings`

### Replacing a stub with a real implementation
All ABCs (`LongTermMemory`, `EmbeddingService`, `MarketPerception`, `ForecastingEngine`) are designed for drop-in replacement — swap the concrete class, callers are unchanged.
