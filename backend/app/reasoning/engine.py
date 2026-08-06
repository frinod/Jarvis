"""JARVIS OS - Reasoning Engine"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from datetime import datetime


class ReasoningStrategy(str, Enum):
    CHAIN_OF_THOUGHT = "chain_of_thought"
    TREE_OF_THOUGHT = "tree_of_thought"
    REACT = "react"  # Reasoning + Acting
    PLAN_AND_EXECUTE = "plan_and_execute"


@dataclass
class ThoughtStep:
    content: str
    confidence: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Plan:
    goal: str
    steps: List[str]
    current_step: int = 0
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)


class ReasoningEngine:
    """Internal reasoning engine that thinks before responding."""

    def __init__(self):
        self._thought_chain: List[ThoughtStep] = []
        self._active_plan: Optional[Plan] = None

    def think(self, thought: str, confidence: float = 0.7) -> ThoughtStep:
        step = ThoughtStep(content=thought, confidence=confidence)
        self._thought_chain.append(step)
        return step

    def create_plan(self, goal: str, steps: List[str]) -> Plan:
        self._active_plan = Plan(goal=goal, steps=steps)
        return self._active_plan

    def advance_plan(self) -> Optional[str]:
        if not self._active_plan or self._active_plan.current_step >= len(self._active_plan.steps):
            return None
        step = self._active_plan.steps[self._active_plan.current_step]
        self._active_plan.current_step += 1
        if self._active_plan.current_step >= len(self._active_plan.steps):
            self._active_plan.status = "completed"
        return step

    def estimate_confidence(self, factors: list[float]) -> float:
        if not factors:
            return 0.5
        return sum(factors) / len(factors)

    def decompose_goal(self, goal: str) -> List[str]:
        """Placeholder for LLM-powered goal decomposition."""
        return [f"Analyze: {goal}", f"Plan approach for: {goal}",
                f"Execute: {goal}", f"Verify: {goal}"]

    def reflect(self) -> dict:
        if not self._thought_chain:
            return {"status": "no_thoughts"}
        avg_confidence = sum(t.confidence for t in self._thought_chain) / len(self._thought_chain)
        return {
            "total_thoughts": len(self._thought_chain),
            "avg_confidence": round(avg_confidence, 2),
            "last_thought": self._thought_chain[-1].content,
            "plan_status": self._active_plan.status if self._active_plan else "no_plan"
        }

    def clear_chain(self):
        self._thought_chain = []
