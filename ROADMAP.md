# JARVIS OS — Roadmap

**Current Version**: v0.6.0  
**Current Status**: Phase 6 Complete — AI Cognition Runtime ✅

---

## Completed Phases

| Phase   | Name                        | Version | Status |
|---------|-----------------------------|---------|--------|
| Phase 1 | Market Data Foundation      | v0.1.0  | ✅     |
| Phase 2 | Module Migration            | v0.2.0  | ✅     |
| Phase 3 | Validation                  | v0.3.0  | ✅     |
| Phase 4 | Cleanup                     | v0.4.0  | ✅     |
| Phase 5 | Configuration Kernel        | v0.5.0  | ✅     |
| Phase 5.5 | Infrastructure Kernel     | v0.5.5  | ✅     |
| Phase 6 | AI Cognition Runtime        | v0.6.0  | ✅     |

---

## Phase 7 — Real Integrations

**Target version**: v0.7.0  
**Status**: 🔜 Awaiting approval

### 7A — Vector Memory (Qdrant)
Replace `InMemoryLongTermMemory` with a real Qdrant vector store.

- [ ] `QdrantLongTermMemory(LongTermMemory)` — store/search/get/delete via Qdrant client
- [ ] `SentenceTransformerEmbeddingService(EmbeddingService)` — replace bag-of-words with real embeddings
- [ ] Memory persistence across sessions
- [ ] Semantic search with cosine similarity threshold
- [ ] Memory TTL and eviction policy

### 7B — Real Market Perception
Replace `InMemoryMarketPerception` with live data.

- [ ] `LiveMarketPerception(MarketPerception)` — wires to `MarketDataService`
- [ ] `LiveNewsPerception(NewsPerception)` — real news feed integration
- [ ] `LiveSentimentPerception(SentimentPerception)` — NLP sentiment on live news
- [ ] Perception caching layer (TTL-based)

### 7C — Real Forecasting
Replace `MockForecastingEngine` with the existing XGBoost models.

- [ ] `XGBoostForecastingEngine(ForecastingEngine)` — loads `.pkl` models from `backend/models/`
- [ ] Feature pipeline: `FeatureStore.build_from_bundles()` → XGBoost input
- [ ] Confidence calibration from model probability outputs
- [ ] Model hot-reload without restart

### 7D — Parallel Workflow Execution
Replace sequential workflow loop with `asyncio.gather()`.

- [ ] `WorkflowEngine` — detect independent nodes (no shared `depends_on`)
- [ ] Execute independent nodes in parallel via `asyncio.gather()`
- [ ] Merge results back into `PipelineContext`
- [ ] No data model changes needed (`WorkflowNode.depends_on` already supports DAG)

### 7E — Agent Registry + Routing
Wire agents into the runtime pipeline.

- [ ] `AgentRegistry` — register/discover agents by capability
- [ ] `AgentRouter` — select best agent for a given `PipelineContext`
- [ ] Multi-agent collaboration (Planner decomposes → Analyst + Researcher execute)
- [ ] Agent result aggregation

---

## Phase 8 — Production Hardening

**Target version**: v0.8.0  
**Status**: 🔜 Planned

### 8A — Infrastructure
- [ ] Python 3.11+ migration (drop 3.7 compatibility)
- [ ] PostgreSQL migration (replace SQLite)
- [ ] Redis caching layer (replace in-memory caches)
- [ ] Alembic migrations for all models

### 8B — Security
- [ ] OAuth2 / API key rotation
- [ ] Rate limiting per endpoint
- [ ] Input sanitisation for all LLM prompts
- [ ] Secrets scanning in CI

### 8C — Observability
- [ ] Structured logging (JSON) with correlation IDs
- [ ] Prometheus metrics export
- [ ] Distributed tracing (OpenTelemetry)
- [ ] Alerting on error rate / latency thresholds

### 8D — Deployment
- [ ] Production Docker images (multi-stage builds)
- [ ] Kubernetes Helm chart
- [ ] GitHub Actions: build → test → push → deploy
- [ ] Health check endpoints for k8s liveness/readiness probes

---

## Phase 9 — Advanced AI Features

**Target version**: v0.9.0  
**Status**: 🔜 Planned

- [ ] Fine-tuned JARVIS persona model
- [ ] Multi-modal input (charts as images → vision model)
- [ ] Autonomous strategy discovery (agent proposes new TA rules)
- [ ] Backtesting integration with AI-generated strategies
- [ ] Real-time voice with sub-200ms latency
- [ ] Mobile app (React Native)

---

## Phase 10 — v1.0 Release

**Target version**: v1.0.0  
**Status**: 🔜 Planned

- [ ] Full documentation site
- [ ] Plugin marketplace
- [ ] Multi-user support
- [ ] Live trading integration (Angel One SmartAPI)
- [ ] Performance: 1000 req/s sustained
- [ ] 99.9% uptime SLA

---

## Technical Debt Backlog

| Item                                    | Blocking Phase |
|-----------------------------------------|----------------|
| `InMemoryLongTermMemory` → Qdrant       | 7A             |
| `SimpleEmbeddingService` → SentenceTransformer | 7A      |
| `MockForecastingEngine` → XGBoost       | 7C             |
| `InMemoryMarketPerception` → live feed  | 7B             |
| Sequential workflow → parallel          | 7D             |
| Python 3.7.9 → 3.11+                   | 8A             |
| SQLite → PostgreSQL                     | 8A             |
| JWT → OAuth2                            | 8B             |

---

## Architecture Change Proposals (ACP) Required For

- Any new package under `app/core/`, `app/config/`, `app/resilience/`
- Any public API change (endpoint signature, response schema)
- Any breaking change to `PipelineContext`, `BaseAgent`, `WorkflowNode`
- Any new external dependency (new pip package)
- Any security-sensitive change
