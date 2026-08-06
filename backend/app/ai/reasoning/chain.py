"""
app/ai/reasoning/chain.py
==========================
ChainOfThought -- structured step-by-step reasoning over an ExecutionContext.

Design
------
  - ChainOfThought.think() produces a sequence of ThoughtSteps.
  - Each step has a content string and a confidence score (0.0–1.0).
  - The chain is built from context: user input, memory, skill/tool results.
  - No LLM calls in this module -- reasoning is pure logic over context.
    LLM calls happen in the Responder stage (execution.py).
  - PipelineReasonerAdapter bridges ChainOfThought to PipelineReasoner ABC
    so ExecutionEngine can inject it without knowing the concrete class.

Domain agnosticism
-------------------
  No domain fields. All domain data arrives via ExecutionContext.metadata.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.ai.runtime.context import ExecutionContext, ThoughtStep
from app.ai.runtime.execution import PipelineReasoner


# ── ChainConfig ───────────────────────────────────────────────────────────────

@dataclass
class ChainConfig:
    """Tuning parameters for ChainOfThought."""
    max_steps:           int   = 5
    base_confidence:     float = 0.6    # starting confidence before evidence
    memory_boost:        float = 0.05   # per memory entry that matches query
    skill_boost:         float = 0.08   # per successful skill result
    tool_boost:          float = 0.06   # per successful tool result
    failure_penalty:     float = 0.10   # per failed skill or tool
    max_memory_boost:    float = 0.20   # cap on total memory contribution
    max_evidence_boost:  float = 0.30   # cap on total skill+tool contribution


# ── ChainOfThought ────────────────────────────────────────────────────────────

class ChainOfThought:
    """
    Builds a structured reasoning chain from an ExecutionContext.

    Steps are generated from the available evidence:
      Step 0 -- understand the goal
      Step 1 -- assess memory context
      Step 2 -- assess skill/tool results
      Step 3 -- synthesise evidence
      Step 4 -- form conclusion

    Confidence is computed incrementally: each step's confidence
    reflects the cumulative evidence available at that point.

    Usage
    -----
        cot    = ChainOfThought()
        chain  = cot.think(ctx)
        final  = chain[-1].confidence if chain else 0.5
    """

    def __init__(self, config: Optional[ChainConfig] = None):
        self._cfg = config or ChainConfig()

    def think(self, ctx: ExecutionContext) -> List[ThoughtStep]:
        """
        Produce a reasoning chain for the current context.
        Populates ctx.thought_chain and ctx.confidence.
        Returns the chain for inspection.
        """
        steps: List[ThoughtStep] = []
        cfg = self._cfg

        # Step 0: understand the goal
        goal = ctx.active_goal or ctx.user_input
        steps.append(ThoughtStep(
            content=f"Goal: {goal[:200]}",
            confidence=cfg.base_confidence,
            step_index=0,
        ))

        # Step 1: assess memory context
        mem_count = len(ctx.memory_context)
        mem_boost = min(mem_count * cfg.memory_boost, cfg.max_memory_boost)
        mem_conf  = min(1.0, cfg.base_confidence + mem_boost)
        mem_note  = (
            f"Retrieved {mem_count} memory entries -- context enriched."
            if mem_count > 0
            else "No memory context available -- reasoning from input only."
        )
        steps.append(ThoughtStep(
            content=f"Memory: {mem_note}",
            confidence=mem_conf,
            step_index=1,
        ))

        # Step 2: assess skill and tool results
        skill_ok  = sum(1 for r in ctx.skill_results.values() if r.success)
        skill_bad = len(ctx.skill_results) - skill_ok
        tool_ok   = sum(1 for r in ctx.tool_results.values() if r.success)
        tool_bad  = len(ctx.tool_results) - tool_ok

        evidence_boost = min(
            skill_ok * cfg.skill_boost + tool_ok * cfg.tool_boost,
            cfg.max_evidence_boost,
        )
        evidence_penalty = (skill_bad + tool_bad) * cfg.failure_penalty
        evidence_conf = min(1.0, max(0.0, mem_conf + evidence_boost - evidence_penalty))

        evidence_note = (
            f"{skill_ok} skill(s) and {tool_ok} tool(s) succeeded"
            + (f"; {skill_bad + tool_bad} failed" if skill_bad + tool_bad > 0 else "")
            + "."
        )
        steps.append(ThoughtStep(
            content=f"Evidence: {evidence_note}",
            confidence=evidence_conf,
            step_index=2,
        ))

        # Step 3: synthesise
        synthesis = self._synthesise(ctx, evidence_conf)
        steps.append(ThoughtStep(
            content=f"Synthesis: {synthesis}",
            confidence=evidence_conf,
            step_index=3,
        ))

        # Step 4: conclusion
        final_conf = round(evidence_conf, 3)
        steps.append(ThoughtStep(
            content=f"Conclusion: Confidence {final_conf:.0%}. Ready to respond.",
            confidence=final_conf,
            step_index=4,
        ))

        ctx.thought_chain = steps
        ctx.confidence    = final_conf
        return steps

    def _synthesise(self, ctx: ExecutionContext, confidence: float) -> str:
        """Build a one-line synthesis summary from available evidence."""
        parts = []
        if ctx.memory_context:
            parts.append(f"{len(ctx.memory_context)} memory entries")
        if ctx.skill_results:
            parts.append(f"{len(ctx.skill_results)} skill result(s)")
        if ctx.tool_results:
            parts.append(f"{len(ctx.tool_results)} tool result(s)")
        if not parts:
            return "Reasoning from user input alone."
        return "Combining " + ", ".join(parts) + f" at {confidence:.0%} confidence."

    def final_confidence(self, chain: List[ThoughtStep]) -> float:
        """Extract the final confidence from a completed chain."""
        return chain[-1].confidence if chain else 0.5


# ── PipelineReasonerAdapter ───────────────────────────────────────────────────

class PipelineReasonerAdapter(PipelineReasoner):
    """
    Bridges ChainOfThought to the PipelineReasoner ABC.
    Injected into ExecutionEngine as the reasoner collaborator.
    """

    def __init__(self, chain_of_thought: Optional[ChainOfThought] = None):
        self._cot = chain_of_thought or ChainOfThought()

    async def reason(self, ctx: ExecutionContext) -> None:
        self._cot.think(ctx)
