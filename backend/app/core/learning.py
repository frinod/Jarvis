"""JARVIS OS - Continuous Learning Module"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from app.memory.manager import MemoryManager, MemoryType


@dataclass
class InteractionAnalysis:
    success: bool
    what_happened: str
    what_worked: Optional[str] = None
    what_failed: Optional[str] = None
    improvement: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class LearningEngine:
    """Analyzes interactions and improves future behavior."""

    def __init__(self, memory: MemoryManager):
        self.memory = memory
        self._analyses: List[InteractionAnalysis] = []

    async def analyze_interaction(self, user_input: str, response: str,
                                  feedback: Optional[str] = None) -> InteractionAnalysis:
        success = feedback != "negative" if feedback else True
        analysis = InteractionAnalysis(
            success=success,
            what_happened=f"User asked: {user_input[:100]}",
            what_worked=f"Response provided: {response[:100]}" if success else None,
            what_failed=f"User was unsatisfied" if not success else None,
            improvement="Adjust response style" if not success else None,
        )
        self._analyses.append(analysis)

        # Store learning in semantic memory
        if not success and analysis.improvement:
            await self.memory.remember(
                f"Learning: {analysis.improvement} (context: {user_input[:50]})",
                MemoryType.SEMANTIC,
                importance=0.8,
                metadata={"type": "learning", "success": success}
            )
        return analysis

    def get_success_rate(self, last_n: int = 50) -> float:
        recent = self._analyses[-last_n:]
        if not recent:
            return 1.0
        return sum(1 for a in recent if a.success) / len(recent)

    def get_insights(self) -> dict:
        return {
            "total_interactions": len(self._analyses),
            "success_rate": self.get_success_rate(),
            "recent_improvements": [
                a.improvement for a in self._analyses[-10:] if a.improvement
            ]
        }
