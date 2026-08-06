# Changelog

All notable changes to JARVIS OS are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v0.6.0] — 2024 — AI Cognition Runtime Complete

### Phase 6D — Agent Framework
**202 new tests | 1459/1459 total passing**

#### Added
- `BaseAgent` ABC — 7-method contract (can_handle, plan, execute, verify, confidence, explain, learn), lifecycle hooks, metrics
- `AnalystAgent` — capabilities: analysis / technical_analysis / market_context
- `ResearcherAgent` — capabilities: research / news / fundamentals / question
- `TraderAgent` — capabilities: trading / signal_generation / execution; produces `TradeSignal` (BUY/SELL/HOLD/NEUTRAL) stored in `AgentResult.metadata["trade_signal"]`
- `PlannerAgent` — capabilities: planning / task / decomposition
- `BaseSkill` ABC + `SkillRegistry` — pure sync, error-isolated skill execution
- `BaseTool` ABC + `AIToolRegistry` — RBAC allowed_roles, asyncio timeout, per-tool metrics
- `MarketPerception` ABC + `InMemoryMarketPerception` — `PerceptionBundle` dataclass
- `NewsPerception` ABC + `InMemoryNewsPerception` — `NewsItem` dataclass
- `SentimentPerception` ABC + `InMemorySentimentPerception` — `SentimentScore` with `from_score()` classmethod
- `FeatureStore` — numeric extraction from perception bundles, `FeatureVector` dataclass
- `ForecastingEngine` ABC + `MockForecastingEngine` — configurable direction/magnitude/confidence
- `ConfidenceScorer` — weighted scoring (prediction 50%, TA signal 30%, sentiment 20%)

#### Test files added
- `test_6d_agents_base.py` (28 tests)
- `test_6d_agents_domain.py` (40 tests)
- `test_6d_skills.py` (22 tests)
- `test_6d_tools.py` (22 tests)
- `test_6d_perception.py` (36 tests)
- `test_6d_prediction.py` (30 tests)
- `test_6d_integration.py` (24 tests)

---

### Phase 6C — Reasoning Engine
**80 new tests | 1258/1258 total passing**

#### Added
- `ChainOfThought` — 5-step reasoning chain from context evidence; memory/skill/tool confidence boosts
- `PipelineReasonerAdapter` — bridges to `PipelineReasoner` ABC
- `Reflection` + `VerificationResult` — evaluates chain length, confidence, stability, evidence
- `PipelineVerifierAdapter` — bridges to `PipelineVerifier` ABC
- `ReasoningPlanner` — keyword-based intent detection (question/task/analysis/general), step templates per intent
- `PipelinePlannerAdapter` — sets `ctx.active_goal` and `ctx.intent_type`
- `PromptTemplate` — render / render_safe with variable substitution
- `TemplateRegistry` — 6 built-in templates: system_base, system_with_memory, reasoning_chain, retry_with_critique, verification, summarise_memory
- `SystemPromptBuilder` — assembles [system, history, memory, thought_chain, user_input] message list
- `PipelineResponderAdapter` — calls LLMGateway, writes ctx.response / ctx.explanation

#### Test files added
- `test_6c_reasoning.py` (80 tests)

---

### Phase 6B — Memory System
**77 new tests | 1178/1178 total passing**

#### Added
- `MemoryEntry` dataclass — id, content, role, importance, timestamp, session_id, embedding, metadata
- `MemoryRole` enum — USER / ASSISTANT / SYSTEM / TOOL
- `ShortTermMemory` — deque ring buffer (maxlen=50), add/search/recent/clear/stats
- `ShortTermMemoryAdapter` — bridges to `PipelineMemoryProvider`
- `LongTermMemory` ABC + `InMemoryLongTermMemory` — dict-backed, importance_threshold=0.6
- `SearchResult` dataclass
- `EmbeddingService` ABC — encode(), similarity(), top_k()
- `SimpleEmbeddingService` — bag-of-words TF, L2-normalised cosine, lazy vocab
- `MemoryPipelineProvider` — wires STM + LTM + embeddings; deduplicates by entry id; graceful degradation

#### Test files added
- `test_6b_memory.py` (77 tests)

---

### Phase 6A — AI Runtime Core
**378 tests | 1101/1101 total passing**

#### Added
- `AIRuntime` facade — top-level entry point wiring Brain → Coordinator → ExecutionEngine
- `Brain` — cognitive controller, routes requests to runtime
- `Coordinator` — orchestrates multi-step workflows
- `WorkflowEngine` — DAG-based workflow execution (`WorkflowNode.depends_on`)
- `ExecutionEngine` — step-by-step pipeline execution
- `LLMGateway` — unified interface to all LLM providers
- `PipelineContext` — shared mutable context across pipeline steps
- `CapabilityMatchPolicy` — reads intent from `goal.metadata.get("intent_type", "")`

#### Test files added
- `test_6a_brain.py`
- `test_6a_context.py`
- `test_6a_coordinator.py`
- `test_6a_execution.py`
- `test_6a_llm_gateway.py`
- `test_6a_runtime.py`
- `test_6a_workflow.py`

---

## [v0.5.5] — Infrastructure Kernel Complete

### Phase 5.5 — Infrastructure Kernel
**Added**
- DI container (`app/core/di/`)
- Event bus (`app/core/events/`)
- Lifecycle manager (`app/core/lifecycle/`)
- Service registry (`app/core/service_registry/`)
- Plugin loader (`app/core/plugins/`)
- Task queue (`app/core/queue/`)
- Scheduler (`app/core/scheduler/`)
- Worker pool (`app/core/workers/`)
- Health monitor (`app/core/health/`)
- Metrics engine (`app/core/metrics/`)

---

## [v0.5.0] — Configuration Kernel Complete

### Phase 5 — Configuration Kernel
**Added**
- Typed settings with environment validation
- `AppSettings`, `AISettings`, `MarketSettings`, `RiskSettings`
- `BrokerSettings`, `CacheSettings`, `LoggingSettings`
- `environment.py` — environment detection + validation
- `exceptions.py` — typed config exceptions
- `retry_policy.py` — configurable retry with backoff

---

## [v0.4.0] — Cleanup Complete

### Phase 4
- Removed dead code and unused imports
- Standardised module interfaces
- Orchestrator hardening

---

## [v0.3.0] — Validation Complete

### Phase 3
- Module consistency validation
- Provider interface validation
- Performance baseline tests

---

## [v0.2.0] — Module Migration Complete

### Phase 2
- Migrated legacy modules to new package structure
- Standardised provider interfaces

---

## [v0.1.0] — Market Data Foundation

### Phase 1
- Yahoo Finance provider
- Angel One SmartAPI provider
- OHLCV data pipeline
- XGBoost forecasting (49 features, 3-class UP/DOWN/FLAT)
- Technical analysis (20+ indicators)
- Paper trading engine
- FastAPI backend
- Next.js frontend with Iron Man HUD
