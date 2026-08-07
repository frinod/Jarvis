# ADR-003 — RAG Architecture

**Date**: 2026-08-07
**Status**: Proposed
**Deciders**: Project owner
**Research**: [docs/research/7.2-rag-research.md](../research/7.2-rag-research.md)

---

## Context

Phase 6 retrieval is single-stage flat fetch with bag-of-words embeddings,
no re-ranking, no metadata filtering, and no semantic caching. The
`SystemPromptBuilder` injects up to 5 entries truncated by index, not
relevance. Perception data (market, news) is not in the memory pipeline.

JARVIS needs retrieval that is precise enough for financial queries (exact
ticker symbols), fast enough for interactive use, and offline-first.

## Decision

Adopt **Hybrid RAG** as the Phase 7 retrieval architecture:

1. **Hybrid retrieval**: Qdrant sparse (BM25) + dense (sentence-transformers)
   vectors, merged with Reciprocal Rank Fusion. Single Qdrant query.

2. **Re-ranking**: `ReRanker` ABC with `CrossEncoderReRanker` (optional,
   ~100 MB model) and `NoOpReRanker` fallback. Injected into
   `MemoryPipelineProvider`.

3. **Metadata filtering**: `entry_type` tag on every `MemoryEntry`
   (`"conversation"`, `"market_snapshot"`, `"news"`, `"analysis_result"`).
   Agents request specific types; default retrieves all.

4. **Token-budgeted context injection**: `SystemPromptBuilder` injects
   entries in descending relevance order, stopping at 800-token budget.

5. **Semantic caching**: `SemanticCache` in `LLMGateway` or
   `PipelineResponderAdapter`. Threshold 0.92, TTL 5 min (market) /
   30 min (general). Reduces repeated LLM calls for identical queries.

6. **Perception-to-LTM pipeline**: `MarketPerception` and `NewsPerception`
   results stored as `MemoryEntry` objects at end of each request.

## Consequences

**Positive**
- Exact ticker symbol queries benefit from BM25 sparse retrieval.
- Re-ranking improves precision without changing the retrieval interface.
- Metadata filtering prevents market data and conversation turns competing.
- Semantic caching reduces latency and LLM cost for repeated queries.
- All changes are additive — zero existing interface modifications.

**Negative**
- `CrossEncoderReRanker` adds ~100 MB model download (optional).
- Hybrid retrieval requires Qdrant sparse vector support (v1.7+).
- Semantic cache adds memory overhead (~few MB for typical session).

## Alternatives Rejected

- **Graph RAG**: requires knowledge graph infrastructure; high complexity
  for low benefit at Phase 7 corpus size.
- **Hierarchical RAG**: valuable for long documents; Phase 7 corpus is
  primarily short entries.
- **Full iterative agentic RAG**: requires Phase 7 agent framework (ReAct
  loop) to be built first; deferred to Phase 8.
- **Naive RAG only**: already implemented in Phase 6; insufficient precision
  for financial queries.

## Rollback Conditions

- If `qdrant-client` sparse vector API is unstable on Python 3.7/Windows:
  fall back to dense-only retrieval (Qdrant still used, sparse disabled).
- If `CrossEncoderReRanker` model download fails: `NoOpReRanker` is the
  default; system continues without re-ranking.
- If semantic cache causes incorrect responses (false positive hits):
  disable by setting `SemanticCache.enabled = False` in config.

## Review Checkpoint

After implementing hybrid retrieval, run `RetrievalEvaluator` against the
labelled test set. Recall@5 must be ≥ 0.80 before proceeding to Phase 8
retrieval work.
