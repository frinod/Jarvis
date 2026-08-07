# ADR-007 — Market Intelligence Integration

**Date**: 2026-08-07
**Status**: Proposed
**Research**: [docs/research/7.6-market-intelligence.md](../research/7.6-market-intelligence.md)

---

## Context

`InMemoryMarketPerception` and `InMemoryNewsPerception` are stubs never
connected to the live Angel One / Yahoo Finance pipeline. The live pipeline
exists in `JarvisOrchestrator._fetch_stock_context()` and works correctly.
Perception data is never stored to LTM.

## Decision

1. **`AngelOneMarketPerception`**: thin wrapper around `fetch_candles()` +
   `compute_technical_analysis()`. Returns `PerceptionBundle` with full TA
   dict and `MarketEvent` list in metadata.

2. **`LiveNewsPerception`**: thin wrapper around `get_market_news()`.
   Maps response to `NewsItem` objects using existing API sentiment field.

3. **`MarketEvent`**: lightweight dataclass (`event_type`, `symbol`,
   `severity`, `description`) parsed from TA dict patterns.

4. **Perception-to-LTM**: `ExecutionEngine._stage_persist()` (optional,
   fire-and-forget) stores `PerceptionBundle` as `entry_type="market_snapshot"`
   and `NewsItem` list as `entry_type="news"`.

5. **Pull model**: perception fetched on-demand per request. Push model
   (background scheduler) deferred to Phase 8.

## Consequences

**Positive**: `AnalystAgent` and `TraderAgent` access live market data;
historical market context accumulates in LTM; zero new external dependencies.

**Negative**: Angel One API rate limits may affect multi-agent requests
(mitigated by per-symbol per-minute cache).

## Alternatives Rejected

- **VADER / RoBERTa sentiment**: existing API sentiment field is sufficient.
- **Push model (Phase 7)**: adds background scheduler complexity; pull
  model is sufficient for Phase 7 request volume.

## Rollback

`AngelOneMarketPerception` and `LiveNewsPerception` implement existing ABCs.
Reverting to `InMemoryMarketPerception` requires only a constructor change.
