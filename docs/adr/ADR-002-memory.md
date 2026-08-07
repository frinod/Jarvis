# ADR-002 — Long-Term Memory Backend

**Date**: 2026-08-07
**Amended**: 2025-07-01
**Status**: Accepted
**Deciders**: Project owner
**Research**: [docs/research/7.1-memory-research.md](../research/7.1-memory-research.md)

---

## Context

Phase 6 uses `InMemoryLongTermMemory` (dict-backed, lost on restart) and
`SimpleEmbeddingService` (bag-of-words TF, poor semantic quality).
Phase 7 requires persistent, semantically-searchable long-term memory.

## Decision

Replace `InMemoryLongTermMemory` with `QdrantLongTermMemory` (Qdrant local
file mode). Replace `SimpleEmbeddingService` with
`SentenceTransformerEmbeddingService` using `all-MiniLM-L6-v2`.

Both replacements implement existing ABCs. No callers change.

## Consequences

**Positive**
- Persistent memory survives restarts.
- Semantically meaningful retrieval replaces substring matching.
- 80 MB model, fully offline, Python 3.7 compatible.
- Zero interface changes — all 1517 tests remain valid.

**Negative**
- ~80 MB model download on first run.
- Qdrant adds a new dependency (`qdrant-client`).
- First-query latency ~200–500 ms while model loads (one-time per process).

## Alternatives Rejected

- **ChromaDB**: less mature, fewer production deployments.
- **FAISS**: no metadata filtering, no built-in persistence API.
- **Pinecone / Weaviate**: cloud dependency or Docker required.
- **Keep InMemoryLongTermMemory**: unacceptable for production (no persistence).

## Memory Resilience Contract

This contract is binding on all Phase 7A implementation. No exception without a new ADR.

### Principle

The AI layer is allowed to degrade gracefully. The trading engine is never allowed to degrade unsafely.

The trading engine must never know Qdrant exists. The dependency direction is one-way and permanent:

```
Trading Engine → Signals → Brain → Memory → Reasoning → Recommendation
```

The reverse direction (`Memory → Trading Engine`) is permanently forbidden.

### Rule MR-1 — Memory is Optional

Memory enhances intelligence. Memory never enables correctness. If the entire memory layer disappears, trading, forecasting, indicators, and execution must continue without degradation. Only context, recall, and personalisation are reduced.

### Rule MR-2 — Empty Memory is a Valid Result

`MemoryUnavailableError` must never propagate into the trading path. Every retrieval call returns a result object. Unavailability is expressed as:

```python
MemoryResult(entries=[], confidence=0.0, source="fallback")
```

### Rule MR-3 — Writes are Best-Effort

A failed `store()` call must log, update health metrics, and continue. It must never cancel a trade, block an analysis, or raise an exception to the caller.

### Rule MR-4 — Read Timeout Budget

Qdrant retrieval timeout is **200 ms**. On timeout, return `MemoryResult(entries=[], confidence=0.0, source="timeout")` immediately. Memory must never become the slowest component in a trading decision path.

### Memory Health States

The memory provider exposes a health state used by Brain to adjust retrieval strategy. No interface changes to callers — Brain reads the state and decides.

| State | Brain behaviour |
|-------|-----------------|
| `Healthy` | Full semantic search, top-k retrieval |
| `Degraded` | Top-5 retrieval only, no reranking |
| `Offline` | Skip retrieval entirely, return fallback |
| `Recovering` | Use in-process cache only |

### Mandatory Test Class

Phase 7A must include `TestMemoryFailureIsolation` covering:

- Qdrant unavailable → trading still produces a valid signal
- Embedding service failure → trading still produces a valid signal
- Memory read timeout → trading still produces a valid signal
- Memory returns `[]` → trading still produces a valid signal
- Memory returns malformed data → trading still produces a valid signal

All five scenarios must pass before Phase 7A is considered complete.

### Permanent Architectural Principle

> Can JARVIS still make a safe decision if every intelligence service is unavailable?

If Qdrant, embeddings, RAG, learning, memory, news, and LLM all fail simultaneously, the verified trading engine, risk engine, paper trading, and execution logic must still produce a safe, deterministic result from market data alone. This is the fault-tolerance baseline.

## Review Checkpoint

Implement `QdrantLongTermMemory` and `SentenceTransformerEmbeddingService`
as drop-in replacements. Run full test suite. If any test fails, revert
to `InMemoryLongTermMemory` and investigate before proceeding.

Run `TestMemoryFailureIsolation` (5 scenarios) before merging to master.
