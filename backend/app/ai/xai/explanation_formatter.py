"""
app/ai/xai/explanation_formatter.py
=====================================
Structured Explanation + ExplanationFormatter.

Design
------
  - Explanation is the intermediate structured object. It carries all
    fields the UI might need: prediction, confidence, top features,
    memory used, agent, decision path, fallback flag, learning applied.
  - ExplanationFormatter renders an Explanation to text, markdown, or JSON.
    The UI can evolve its rendering without changing the explainer.
  - PipelineExplanationWriter is a convenience helper that builds an
    Explanation from an ExecutionContext + FeatureImportance and writes
    the plain-text rendering to ctx.explanation.

Resilience (Rule 11b):
  format_*() methods never raise. Return empty string on failure.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.ai.runtime.context import ExecutionContext
from app.ai.xai.shap_explainer import FeatureImportance

logger = logging.getLogger(__name__)


# ── Explanation ───────────────────────────────────────────────────────────────

@dataclass
class Explanation:
    """
    Structured explanation for one AI decision.

    All fields are optional so callers can populate only what they have.
    ExplanationFormatter renders whichever fields are present.
    """
    prediction:        str                       = ""
    confidence:        float                     = 0.0
    top_features:      List[Tuple[str, float]]   = field(default_factory=list)
    memory_used:       List[str]                 = field(default_factory=list)
    agent_used:        str                       = ""
    decision_path:     List[str]                 = field(default_factory=list)
    fallback_triggered: bool                     = False
    learning_applied:  bool                      = False
    metadata:          Dict[str, Any]            = field(default_factory=dict)

    @classmethod
    def from_context(
        cls,
        ctx:        ExecutionContext,
        importance: Optional[FeatureImportance] = None,
    ) -> "Explanation":
        """Build an Explanation from a completed ExecutionContext."""
        top_features: List[Tuple[str, float]] = []
        if importance:
            top_features = importance.top(5)

        memory_used = [
            getattr(e, "content", str(e))[:80]
            for e in (ctx.memory_context or [])
        ]

        decision_path = [step.content[:120] for step in ctx.thought_chain]

        fallback = bool(ctx.metadata.get("_decision_tree_fired"))
        learning = bool(ctx.metadata.get("_learning_applied"))

        return cls(
            prediction=ctx.response[:200] if ctx.response else "",
            confidence=ctx.confidence,
            top_features=top_features,
            memory_used=memory_used,
            agent_used=ctx.selected_agent,
            decision_path=decision_path,
            fallback_triggered=fallback,
            learning_applied=learning,
        )

    def to_dict(self) -> dict:
        return {
            "prediction":         self.prediction,
            "confidence":         self.confidence,
            "top_features":       self.top_features,
            "memory_used":        self.memory_used,
            "agent_used":         self.agent_used,
            "decision_path":      self.decision_path,
            "fallback_triggered": self.fallback_triggered,
            "learning_applied":   self.learning_applied,
            **self.metadata,
        }


# ── ExplanationFormatter ──────────────────────────────────────────────────────

class ExplanationFormatter:
    """
    Renders an Explanation to text, markdown, or JSON.

    All methods are pure functions — no side effects.
    Never raises (Rule 11b).

    Usage
    -----
        fmt = ExplanationFormatter()
        text = fmt.format_text(explanation)
        md   = fmt.format_markdown(explanation)
        js   = fmt.format_json(explanation)
    """

    def format_text(self, exp: Explanation) -> str:
        """Render to plain text suitable for ctx.explanation."""
        try:
            lines = []
            if exp.prediction:
                lines.append(f"Prediction: {exp.prediction}")
            lines.append(f"Confidence: {exp.confidence:.0%}")
            if exp.agent_used:
                lines.append(f"Agent: {exp.agent_used}")
            if exp.top_features:
                feat_str = ", ".join(
                    f"{name} ({score:.1%})" for name, score in exp.top_features
                )
                lines.append(f"Top features: {feat_str}")
            if exp.memory_used:
                lines.append(f"Memory used: {len(exp.memory_used)} entries")
            if exp.decision_path:
                lines.append(f"Reasoning steps: {len(exp.decision_path)}")
            if exp.fallback_triggered:
                lines.append("Note: decision-tree fallback was triggered.")
            if exp.learning_applied:
                lines.append("Note: learning adjustments applied.")
            return " | ".join(lines)
        except Exception as exc:
            logger.debug("ExplanationFormatter.format_text failed: %s", exc)
            return ""

    def format_markdown(self, exp: Explanation) -> str:
        """Render to markdown for UI display."""
        try:
            parts = [f"**Confidence**: {exp.confidence:.0%}"]
            if exp.agent_used:
                parts.append(f"**Agent**: {exp.agent_used}")
            if exp.top_features:
                rows = "\n".join(
                    f"- `{name}`: {score:.1%}" for name, score in exp.top_features
                )
                parts.append(f"**Top Features**:\n{rows}")
            if exp.decision_path:
                steps = "\n".join(
                    f"{i+1}. {step}" for i, step in enumerate(exp.decision_path)
                )
                parts.append(f"**Reasoning Path**:\n{steps}")
            if exp.fallback_triggered:
                parts.append("⚠️ Decision-tree fallback triggered.")
            if exp.learning_applied:
                parts.append("✅ Learning adjustments applied.")
            return "\n\n".join(parts)
        except Exception as exc:
            logger.debug("ExplanationFormatter.format_markdown failed: %s", exc)
            return ""

    def format_json(self, exp: Explanation) -> str:
        """Render to JSON string."""
        try:
            return json.dumps(exp.to_dict(), ensure_ascii=False, default=str)
        except Exception as exc:
            logger.debug("ExplanationFormatter.format_json failed: %s", exc)
            return "{}"


# ── PipelineExplanationWriter ─────────────────────────────────────────────────

class PipelineExplanationWriter:
    """
    Convenience helper: builds an Explanation from ctx + FeatureImportance
    and writes the plain-text rendering to ctx.explanation.

    Usage
    -----
        writer = PipelineExplanationWriter()
        writer.write(ctx, importance=shap_result)
    """

    def __init__(self) -> None:
        self._fmt = ExplanationFormatter()

    def write(
        self,
        ctx:        ExecutionContext,
        importance: Optional[FeatureImportance] = None,
    ) -> Explanation:
        """
        Build Explanation, write text to ctx.explanation, return Explanation.
        Never raises.
        """
        try:
            exp = Explanation.from_context(ctx, importance=importance)
            ctx.explanation = self._fmt.format_text(exp)
            ctx.metadata["_explanation"] = exp.to_dict()
            return exp
        except Exception as exc:
            logger.debug("PipelineExplanationWriter.write failed: %s", exc)
            return Explanation()
