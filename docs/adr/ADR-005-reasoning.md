# ADR-005 — Reasoning Architecture

**Date**: 2026-08-07
**Status**: Proposed
**Research**: [docs/research/7.4-reasoning-research.md](../research/7.4-reasoning-research.md)

---

## Context

Phase 6 `ChainOfThought` produces no LLM reasoning — all steps are pure
arithmetic over context counts. `ReasoningPlanner` uses first-word keyword
matching. The `retry_with_critique` template exists but is never used.

## Decision

1. **LLM-generated CoT**: `LLMReasonerAdapter` replaces `PipelineReasonerAdapter`
   for `AnalystAgent` and `TraderAgent`. Prompts the LLM with "think step by
   step" instruction. JSON-mode output for supported providers.

2. **LLM intent classification**: `LLMPlannerAdapter` replaces keyword
   matching with a structured LLM classification prompt. Falls back to
   keyword matching when LLM unavailable.

3. **LLM self-critique**: wire `retry_with_critique` template into
   `ExecutionEngine._stage_reason()` when `should_retry=True`. Injects
   critique into next reasoning attempt.

4. **Fallback**: `ChainOfThought` (pure logic) remains as fallback when
   no LLM is available. All existing tests continue to pass.

## Consequences

**Positive**: reasoning quality improves significantly for complex requests;
intent classification accuracy improves.

**Negative**: LLM intent classification adds ~100–200 ms; CoT adds 1 LLM
call per complex request; token usage increases.

## Alternatives Rejected

- **Self-Consistency (SC-CoT)**: 3–5× LLM calls; cost unacceptable.
- **Tree of Thoughts**: requires parallel execution (Phase 7C dependency).
- **Graph of Thoughts**: requires ToT first.

## Rollback

`LLMReasonerAdapter` and `LLMPlannerAdapter` are injected as optional
collaborators. Setting them to `None` reverts to Phase 6 behaviour.
