"""
app/ai/reasoning/reflection.py
================================
Reflection -- self-critique and verification of a reasoning chain.

Design
------
  - Reflection.evaluate() inspects a completed thought chain and produces
    a VerificationResult: passed, critique, should_retry.
  - Pure logic -- no LLM calls, no I/O.
  - PipelineVerifierAdapter bridges Reflection to PipelineVerifier ABC.
  - Retry decision is based on configurable thresholds, not heuristics.

Domain agnosticism
-------------------
  No domain fields. Operates on ThoughtStep confidence scores only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.ai.runtime.context import ExecutionContext, ThoughtStep
from app.ai.runtime.execution import PipelineVerifier


# ── VerificationResult ────────────────────────────────────────────────────────

@dataclass
class VerificationResult:
    """
    Output of one Reflection pass.

    passed       -- True if the reasoning chain meets the quality bar
    should_retry -- True if the engine should re-run reasoning
    critique     -- human-readable explanation of the verdict
    confidence   -- final confidence score from the chain
    issues       -- list of specific problems found (for debugging)
    """
    passed:       bool
    should_retry: bool
    critique:     str
    confidence:   float
    issues:       List[str] = field(default_factory=list)


# ── ReflectionConfig ──────────────────────────────────────────────────────────

@dataclass
class ReflectionConfig:
    """Thresholds for the Reflection quality checks."""
    min_confidence:      float = 0.4    # below this: always retry
    good_confidence:     float = 0.7    # above this: always pass
    min_steps:           int   = 2      # chain must have at least this many steps
    max_confidence_drop: float = 0.3    # max allowed drop between consecutive steps


# ── Reflection ────────────────────────────────────────────────────────────────

class Reflection:
    """
    Evaluates a completed reasoning chain and decides whether to retry.

    Checks performed:
      1. Chain length -- must have at least min_steps
      2. Final confidence -- below min_confidence triggers retry
      3. Confidence drop -- large drops between steps indicate instability
      4. Failed evidence -- many failed skills/tools lower trust

    Usage
    -----
        reflection = Reflection()
        result     = reflection.evaluate(ctx)
        if result.should_retry:
            # inject result.critique back into context and re-reason
    """

    def __init__(self, config: Optional[ReflectionConfig] = None):
        self._cfg = config or ReflectionConfig()

    def evaluate(self, ctx: ExecutionContext) -> VerificationResult:
        """
        Evaluate the current thought chain in ctx.
        Sets ctx.critique to the critique string.
        Returns a VerificationResult.
        """
        chain  = ctx.thought_chain
        cfg    = self._cfg
        issues: List[str] = []

        # Check 1: chain length
        if len(chain) < cfg.min_steps:
            issues.append(f"Reasoning chain too short ({len(chain)} steps, min {cfg.min_steps})")

        # Check 2: final confidence
        final_conf = chain[-1].confidence if chain else 0.0

        if final_conf < cfg.min_confidence:
            issues.append(f"Confidence {final_conf:.2f} below minimum {cfg.min_confidence}")

        # Check 3: confidence stability (no large drops)
        if len(chain) >= 2:
            for i in range(1, len(chain)):
                drop = chain[i - 1].confidence - chain[i].confidence
                if drop > cfg.max_confidence_drop:
                    issues.append(
                        f"Confidence drop of {drop:.2f} between steps {i-1} and {i}"
                    )

        # Check 4: evidence quality
        failed = sum(1 for r in ctx.tool_results.values() if not r.success)
        failed += sum(1 for r in ctx.skill_results.values() if not r.success)
        if failed > 0 and final_conf < cfg.good_confidence:
            issues.append(f"{failed} evidence source(s) failed with low confidence")

        # Verdict
        passed       = len(issues) == 0
        should_retry = (
            not passed
            and final_conf < cfg.good_confidence
            and len(chain) >= cfg.min_steps   # don't retry an empty chain
        )

        if passed:
            critique = f"Reasoning verified. Confidence {final_conf:.0%}."
        elif should_retry:
            critique = "Retry recommended: " + "; ".join(issues) + "."
        else:
            critique = "Issues found but retry not warranted: " + "; ".join(issues) + "."

        ctx.critique = critique

        return VerificationResult(
            passed=passed,
            should_retry=should_retry,
            critique=critique,
            confidence=final_conf,
            issues=issues,
        )

    def score(self, chain: List[ThoughtStep]) -> float:
        """Return the final confidence from a chain without modifying context."""
        return chain[-1].confidence if chain else 0.0


# ── PipelineVerifierAdapter ───────────────────────────────────────────────────

class PipelineVerifierAdapter(PipelineVerifier):
    """
    Bridges Reflection to the PipelineVerifier ABC.
    Injected into ExecutionEngine as the verifier collaborator.
    Returns True (should retry) when Reflection says so.
    """

    def __init__(self, reflection: Optional[Reflection] = None):
        self._reflection = reflection or Reflection()

    async def verify(self, ctx: ExecutionContext) -> bool:
        result = self._reflection.evaluate(ctx)
        return result.should_retry
