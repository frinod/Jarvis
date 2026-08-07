# ADR-001 — Brain as Central Cognitive Controller

**Date**: 2026-07-25
**Status**: Accepted
**Phase**: 6A

---

## Context

JARVIS needed a component to own goal lifecycle, session state, confidence
aggregation, and reflection without containing domain logic.

## Decision

`Brain` is the central cognitive controller. It creates one `Goal` per
request, delegates execution to `ExecutionEngine`, and reflects on every
completed result. It contains zero domain knowledge.

## Consequences

- Clean separation: Brain owns goals, ExecutionEngine owns pipeline stages.
- `BrainCapabilities` flags (`supports_parallel_goals`, `supports_goal_tree`)
  allow progressive Phase 7 rollout without interface changes.
- Reflection is pure logic — no LLM calls — keeping Brain fast and testable.

## Alternatives Rejected

- **Monolithic orchestrator**: would mix goal management with pipeline execution.
- **Agent-owned goals**: would scatter goal lifecycle across multiple agents.
