"""
app/ai/reasoning/decision_tree.py
===================================
DecisionTree -- rule-based fallback reasoning when LLM confidence is low.

Design
------
  - DecisionNode: one rule with a condition predicate and a response action.
  - DecisionTree: ordered list of DecisionNodes evaluated top-to-bottom.
    First matching node wins (priority order).
  - DecisionTreeEvaluator: evaluates a tree against an ExecutionContext.
    Returns a DecisionOutcome (matched, response, node_name, confidence).
  - Pure logic -- no LLM calls, no I/O, no domain knowledge.
  - Complements Reflection: Reflection detects problems, DecisionTree
    provides deterministic answers when LLM confidence is too low.

Resilience (Rule 11b):
  evaluate() never raises. Returns DecisionOutcome(matched=False) on any error.

Domain agnosticism:
  Conditions operate on ExecutionContext fields only.
  Domain data travels through ctx.metadata -- never as first-class fields.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from app.ai.runtime.context import ExecutionContext

logger = logging.getLogger(__name__)

# Condition type: takes ExecutionContext, returns bool
ConditionFn = Callable[[ExecutionContext], bool]


# ── DecisionNode ──────────────────────────────────────────────────────────────

@dataclass
class DecisionNode:
    """
    One rule in a DecisionTree.

    name:       human-readable identifier for logging and XAI
    condition:  callable(ctx) -> bool — must be fast, no I/O
    response:   the answer to return when condition matches
    confidence: how confident this rule is (0.0–1.0)
    priority:   lower = evaluated first (default 5)
    """
    name:       str
    condition:  ConditionFn
    response:   str
    confidence: float = 0.7
    priority:   int   = 5
    metadata:   dict  = field(default_factory=dict)


# ── DecisionOutcome ───────────────────────────────────────────────────────────

@dataclass
class DecisionOutcome:
    """
    Result of one DecisionTree evaluation.

    matched:    True if a rule fired
    response:   the rule's response (empty string if no match)
    node_name:  which rule matched (empty if no match)
    confidence: the matched rule's confidence (0.0 if no match)
    """
    matched:    bool
    response:   str   = ""
    node_name:  str   = ""
    confidence: float = 0.0


# ── DecisionTree ──────────────────────────────────────────────────────────────

class DecisionTree:
    """
    Ordered collection of DecisionNodes.

    Nodes are evaluated in ascending priority order (lowest priority int first).
    First matching node wins. Remaining nodes are not evaluated.

    Usage
    -----
        tree = DecisionTree(name="fallback")
        tree.add(DecisionNode(
            name="low_confidence",
            condition=lambda ctx: ctx.confidence < 0.4,
            response="I need more information to answer confidently.",
            confidence=0.5,
            priority=1,
        ))
        outcome = tree.evaluate(ctx)
        if outcome.matched:
            ctx.response = outcome.response
    """

    def __init__(self, name: str = "default") -> None:
        self.name   = name
        self._nodes: List[DecisionNode] = []

    def add(self, node: DecisionNode) -> None:
        """Add a node. Tree is re-sorted by priority on each add."""
        self._nodes.append(node)
        self._nodes.sort(key=lambda n: n.priority)

    def evaluate(self, ctx: ExecutionContext) -> DecisionOutcome:
        """
        Evaluate all nodes in priority order. Return first match.
        Never raises (Rule 11b).
        """
        try:
            for node in self._nodes:
                try:
                    if node.condition(ctx):
                        return DecisionOutcome(
                            matched=True,
                            response=node.response,
                            node_name=node.name,
                            confidence=node.confidence,
                        )
                except Exception as exc:
                    logger.debug("DecisionNode '%s' condition raised: %s", node.name, exc)
                    continue
        except Exception as exc:
            logger.warning("DecisionTree.evaluate failed: %s", exc)
        return DecisionOutcome(matched=False)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def node_names(self) -> List[str]:
        return [n.name for n in self._nodes]


# ── DecisionTreeEvaluator ─────────────────────────────────────────────────────

class DecisionTreeEvaluator:
    """
    Evaluates a DecisionTree against an ExecutionContext and optionally
    writes the outcome back to ctx.response when matched.

    Injected into ExecutionEngine or Brain as a post-reasoning fallback.
    Only fires when ctx.confidence is below the configured threshold.

    Usage
    -----
        evaluator = DecisionTreeEvaluator(tree=tree, confidence_threshold=0.4)
        outcome   = evaluator.apply(ctx)
        # If outcome.matched, ctx.response has been set to the rule response.
    """

    def __init__(
        self,
        tree:                 DecisionTree,
        confidence_threshold: float = 0.4,
        write_to_ctx:         bool  = True,
    ) -> None:
        self._tree      = tree
        self._threshold = confidence_threshold
        self._write     = write_to_ctx

    def apply(self, ctx: ExecutionContext) -> DecisionOutcome:
        """
        Apply the tree if ctx.confidence is below threshold.
        If write_to_ctx=True and a rule matches, sets ctx.response.
        Never raises.
        """
        try:
            if ctx.confidence >= self._threshold:
                return DecisionOutcome(matched=False)
            outcome = self._tree.evaluate(ctx)
            if outcome.matched and self._write:
                ctx.response = outcome.response
                ctx.metadata["_decision_tree_fired"] = {
                    "node":       outcome.node_name,
                    "confidence": outcome.confidence,
                    "tree":       self._tree.name,
                }
            return outcome
        except Exception as exc:
            logger.warning("DecisionTreeEvaluator.apply failed: %s", exc)
            return DecisionOutcome(matched=False)


# ── Built-in rule factory ─────────────────────────────────────────────────────

def build_default_tree() -> DecisionTree:
    """
    Returns a DecisionTree with sensible default fallback rules.
    These are generic -- no domain knowledge.

    Rules (in priority order):
      1. empty_input     -- user sent nothing
      2. very_low_conf   -- confidence < 0.2, no memory
      3. failed_tools    -- all tools failed
      4. no_memory       -- no memory context and low confidence
    """
    tree = DecisionTree(name="default_fallback")

    tree.add(DecisionNode(
        name="empty_input",
        condition=lambda ctx: not ctx.user_input.strip(),
        response="Please provide a question or request.",
        confidence=0.95,
        priority=1,
    ))

    tree.add(DecisionNode(
        name="very_low_confidence",
        condition=lambda ctx: ctx.confidence < 0.2 and not ctx.memory_context,
        response="I don't have enough context to answer confidently. Could you provide more detail?",
        confidence=0.5,
        priority=2,
    ))

    tree.add(DecisionNode(
        name="all_tools_failed",
        condition=lambda ctx: (
            bool(ctx.tool_results)
            and all(not r.success for r in ctx.tool_results.values())
        ),
        response="The tools I needed are currently unavailable. I'll answer from memory only.",
        confidence=0.4,
        priority=3,
    ))

    tree.add(DecisionNode(
        name="no_memory_low_confidence",
        condition=lambda ctx: not ctx.memory_context and ctx.confidence < 0.35,
        response="I don't have relevant context for this request. Please provide more information.",
        confidence=0.45,
        priority=4,
    ))

    return tree
