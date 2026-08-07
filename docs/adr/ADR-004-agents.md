# ADR-004 — Agent Execution Model

**Date**: 2026-08-07
**Status**: Proposed
**Research**: [docs/research/7.3-agent-research.md](../research/7.3-agent-research.md)

---

## Context

All Phase 6 agents are stubs. `execute()` returns hardcoded strings.
`CapabilityMatchPolicy` scores near-zero. `WorkflowEngine` is sequential only.
Agents cannot call tools from within `execute()`.

## Decision

1. **ReAct execution model**: implement `ReactExecutor` for `TraderAgent`
   and `AnalystAgent`. Thought → Act (tool call) → Observe loop, max 3 iterations.

2. **Native function calling**: `AIToolRegistry.to_schema()` emits
   OpenAI-compatible tool definitions. `LLMGateway` passes them in requests
   for supported providers. Text-based fallback for Ollama.

3. **Parallel workflow**: replace sequential `for node in workflow.nodes`
   with topological sort + `asyncio.gather()` over ready nodes.

4. **Sequential result handoff**: `WorkflowEngine._run_node()` passes
   `node.result` into the next node's `ExecutionContext.metadata`.

5. **Intent fix**: `Brain.process()` copies `ctx.intent_type` into
   `goal.metadata["intent_type"]` after the plan stage (2-line fix).

6. **AgentMetrics feedback**: add `metrics_weight=0.0` to `SelectionWeights`.
   When `AgentMetrics.requests >= 10`, `success_rate` contributes to score.

## Consequences

**Positive**: agents produce real LLM-reasoned responses; parallel workflows
reduce latency; capability scoring works correctly.

**Negative**: ReAct loop adds 1–3 LLM calls per agent request; parallel
execution requires each node to have its own `ExecutionContext`.

## Alternatives Rejected

- **DSPy**: requires labelled outcome dataset not yet available.
- **MCP**: external client exposure not in Phase 7 scope.
- **Full iterative agentic RAG**: requires ReAct loop first (circular).

## Rollback

If `asyncio.gather()` introduces race conditions: revert to sequential loop.
`WorkflowNode` data model is unchanged — rollback is a one-line revert.
