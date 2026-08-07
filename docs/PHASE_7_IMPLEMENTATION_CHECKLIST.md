# Phase 7 Implementation Checklist

**Version**: 1.1  
**Status**: In Progress  
**Started**: 2025-07-01  
**Target**: v0.9.0

This is the live progress tracker for Phase 7. Update checkboxes as work completes. Do not add new items without a corresponding ADR or research reference.

---

## Project Milestones

| Milestone | Description | Status |
|-----------|-------------|--------|
| 1 | Foundation — Core, Config, Infrastructure | ✅ Complete |
| 2 | Verified Trading Engine | ✅ Complete — `v0.7.1-trading-verified` |
| 3 | AI Cognition Runtime | ✅ Complete — `foundation-v1` |
| 4 | Intelligence Layer | 🔄 Phase 7 — in progress |

---

## Capability Milestones (Phase 7 success criteria)

Progress is measured by capabilities, not lines of code.

- [ ] Remembers past trades and conversations
- [ ] Retrieves historical market context by semantic similarity
- [ ] Learns from successful trades
- [ ] Learns from failed trades
- [ ] Explains its reasoning in plain language
- [ ] Explains confidence with feature-level justification
- [ ] Justifies recommendations with retrieved evidence
- [ ] Adapts over time without modifying the frozen trading engine
- [ ] Improves prediction accuracy through feedback loop

---

## System Readiness Review (Post Phase 7)

Scheduled after Phase 7D is tagged. Not a code review — a full System Readiness Review.

| Volume | Scope | Status |
|--------|-------|--------|
| 1 | Architecture — layering, dependencies, package boundaries | ⬜ Pending |
| 2 | Algorithms — trading logic, forecasting, risk calculations | ⬜ Pending |
| 3 | Trading Mathematics — independent formula verification | ⬜ Pending |
| 4 | AI Cognition — memory, reasoning, agent orchestration | ⬜ Pending |
| 5 | Memory — retrieval quality, latency, persistence | ⬜ Pending |
| 6 | Security — secrets, validation, injection risks, dependencies | ⬜ Pending |
| 7 | Performance — hotspots, scalability, memory usage | ⬜ Pending |
| 8 | Production Readiness — logging, health checks, observability, recovery | ⬜ Pending |
| **Overall** | **Go / No-Go for v1.0** | ⬜ Pending |

---

## Phase 7A — Memory & Vector Store

**ADR**: ADR-002-memory.md  
**Research**: 7.1-memory-research.md  
**Target version**: 0.8.0  
**Status**: ⬜ Not started

### Infrastructure
- [ ] Qdrant service running and reachable from backend
- [ ] `QDRANT_URL` and `QDRANT_API_KEY` environment variables documented in `.env.example`
- [ ] `qdrant-client==1.7.x` added to `requirements.txt`
- [ ] `sentence-transformers==2.2.2` added to `requirements.txt`

### Memory Provider (`app/ai/memory/`)
- [ ] `memory_provider.py` — abstract base class `MemoryProvider` with `store()`, `retrieve()`, `delete()`
- [ ] `qdrant_memory.py` — `QdrantMemory(MemoryProvider)` implementation
- [ ] `embedding_service.py` — wraps `sentence-transformers`, returns 384-dim vectors
- [ ] `memory_types.py` — `MemoryEntry` dataclass (id, content, embedding, metadata, timestamp)

### Collections
- [ ] `trade_memory` collection created in Qdrant (cosine distance, 384 dims)
- [ ] `market_memory` collection created in Qdrant
- [ ] `conversation_memory` collection created in Qdrant

### Tests
- [ ] Unit: `embedding_service` returns correct vector shape
- [ ] Unit: `QdrantMemory.store()` round-trips correctly
- [ ] Unit: `QdrantMemory.retrieve()` returns top-k by cosine similarity
- [ ] Integration: store a trade event, retrieve by semantic query
- [ ] Performance: p95 retrieve latency < 100 ms on 10 000 entries
- [ ] **Resilience** (`TestMemoryFailureIsolation` — all 5 required by ADR-002):
  - [ ] Qdrant unavailable → trading signal still produced
  - [ ] Embedding service failure → trading signal still produced
  - [ ] Memory read timeout (>200 ms) → trading signal still produced
  - [ ] Memory returns `[]` → trading signal still produced
  - [ ] Memory returns malformed data → trading signal still produced

### Integration
- [ ] Memory provider wired into `app/core/` via dependency injection
- [ ] `auto_trader.py` emits trade events to memory (read-only interface, no internal modification)
- [ ] All 1517 existing tests still passing after integration

---

## Phase 7B — RAG & Market Intelligence

**ADR**: ADR-003-rag.md  
**Research**: 7.2-rag-research.md, 7.6-market-intelligence.md  
**Target version**: 0.8.1  
**Status**: ⬜ Not started

### RAG Pipeline (`app/ai/rag/`)
- [ ] `retriever.py` — semantic search against Qdrant, returns top-k `MemoryEntry` list
- [ ] `reranker.py` — cross-encoder reranking of retrieved candidates
- [ ] `context_builder.py` — assembles retrieved entries into a prompt context string
- [ ] `semantic_cache.py` — exact + near-duplicate query cache (TTL 5 min)

### Market Intelligence Enhancement
- [ ] RAG context injected into `get_intraday_assistant()` response
- [ ] RAG context injected into `get_ai_discovery()` response
- [ ] Retrieval latency logged per request

### Tests
- [ ] Unit: `retriever` returns correct number of results
- [ ] Unit: `reranker` improves relevance score on synthetic dataset
- [ ] Unit: `semantic_cache` returns cached result on duplicate query
- [ ] Integration: full RAG pipeline returns coherent context for a sample market query
- [ ] Regression: all 1517 + 7A tests passing

---

## Phase 7C — Agent Framework & Reasoning

**ADR**: ADR-004-agents.md, ADR-005-reasoning.md  
**Research**: 7.3-agent-research.md, 7.4-reasoning-research.md  
**Target version**: 0.8.2  
**Status**: ⬜ Not started

### Agent Framework (`app/ai/agents/`)
- [ ] `base_agent.py` — abstract `Agent` with `plan()`, `act()`, `observe()` interface
- [ ] `trade_agent.py` — trading-focused agent, consumes forecaster + regime outputs
- [ ] `research_agent.py` — market research agent, consumes RAG + news
- [ ] `agent_registry.py` — maps agent names to instances, supports hot-reload

### Reasoning Engine (`app/ai/reasoning/`)
- [ ] `chain_of_thought.py` — step-by-step reasoning trace builder
- [ ] `decision_tree.py` — rule-based fallback when LLM confidence is low
- [ ] `reasoning_log.py` — persists reasoning traces to memory store

### Tests
- [ ] Unit: each agent produces a valid `AgentAction` on a synthetic market state
- [ ] Unit: reasoning trace is non-empty and serialisable
- [ ] Integration: `trade_agent` → `forecaster` → `auto_trader` pipeline produces a trade decision without modifying frozen files
- [ ] Regression: all prior tests passing

---

## Phase 7D — XAI & Learning Engine

**ADR**: ADR-006-prediction.md  
**Research**: 7.5-prediction-research.md, 7.7-learning-engine.md, 7.8-xai-research.md  
**Target version**: 0.9.0  
**Status**: ⬜ Not started

### Explainability (`app/ai/xai/`)
- [ ] `shap_explainer.py` — wraps `shap==0.41.x`, produces feature importance for each forecast
- [ ] `explanation_formatter.py` — converts SHAP values to human-readable text
- [ ] `xai_cache.py` — caches explanations by model version + feature hash (TTL 1 h)

### Learning Engine (`app/ai/learning/`)
- [ ] `feedback_collector.py` — records actual trade outcomes vs predicted
- [ ] `model_evaluator.py` — computes rolling accuracy, precision, recall on live trades
- [ ] `retraining_trigger.py` — fires retraining job when accuracy drops below threshold
- [ ] `model_registry.py` — versioned model store, rollback support

### Dependencies
- [ ] `shap==0.41.x` added to `requirements.txt`
- [ ] `torch==1.13.x` (CPU) added to `requirements.txt`

### Tests
- [ ] Unit: `shap_explainer` returns one importance value per feature (49 features)
- [ ] Unit: `feedback_collector` stores outcome and retrieves by trade id
- [ ] Unit: `retraining_trigger` fires correctly when accuracy < threshold
- [ ] Integration: full prediction → explanation → feedback loop on synthetic data
- [ ] Performance: SHAP explanation p95 latency < 500 ms
- [ ] Regression: all prior tests passing

---

## Cross-Phase Gates

These must be true before any sub-phase is considered complete.

| Gate | 7A | 7B | 7C | 7D |
|------|----|----|----|----|
| All prior tests passing | ⬜ | ⬜ | ⬜ | ⬜ |
| New tests added (count ≥ prior + 10) | ⬜ | ⬜ | ⬜ | ⬜ |
| No frozen file modified | ⬜ | ⬜ | ⬜ | ⬜ |
| V&V entry created | ⬜ | ⬜ | ⬜ | ⬜ |
| Git tag created | ⬜ | ⬜ | ⬜ | ⬜ |
| Baseline document updated | ⬜ | ⬜ | ⬜ | ⬜ |

---

## Progress Summary

| Sub-phase | Files | Tests Added | Status |
|-----------|-------|-------------|--------|
| 7A Memory | 0 / 7 | 0 | ⬜ Not started |
| 7B RAG | 0 / 4 | 0 | ⬜ Not started |
| 7C Agents | 0 / 7 | 0 | ⬜ Not started |
| 7D XAI + Learning | 0 / 8 | 0 | ⬜ Not started |

---

## Change Log

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2025-07-01 | Initial checklist created from ADRs 002–006 and research 7.1–7.8 |
| 1.1 | 2025-07-01 | Added project milestone table, capability milestones, System Readiness Review plan |
