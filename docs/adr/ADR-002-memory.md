# ADR-002 — Long-Term Memory Backend

**Date**: 2026-08-07
**Status**: Proposed
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

## Review Checkpoint

Implement `QdrantLongTermMemory` and `SentenceTransformerEmbeddingService`
as drop-in replacements. Run full test suite. If any test fails, revert
to `InMemoryLongTermMemory` and investigate before proceeding.
