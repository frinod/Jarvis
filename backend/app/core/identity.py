"""JARVIS OS - Core Identity and Self-Awareness Module"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class FocusState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    EXECUTING = "executing"
    SPEAKING = "speaking"
    LEARNING = "learning"
    ANALYZING = "analyzing"
    MONITORING = "monitoring"
    AWAITING_CONFIRMATION = "awaiting_confirmation"


@dataclass
class Identity:
    name: str = "JARVIS"
    full_name: str = "Just A Rather Very Intelligent System"
    version: str = "2.0.0"
    role: str = "Advanced Personal AI Operating System"
    creator: str = "Sir"
    personality_traits: List[str] = field(default_factory=lambda: [
        "british_wit", "dry_humor", "loyal", "calm_under_pressure",
        "respectful", "highly_confident", "analytically_precise",
        "proactive", "protective", "emotionally_intelligent"
    ])


@dataclass
class InternalState:
    focus: FocusState = FocusState.IDLE
    confidence: float = 0.8
    current_goal: Optional[str] = None
    current_task: Optional[str] = None
    reasoning_trace: List[dict] = field(default_factory=list)
    active_agents: List[str] = field(default_factory=list)
    last_interaction: Optional[datetime] = None
    session_start: datetime = field(default_factory=datetime.utcnow)
    interaction_count: int = 0


class JarvisCore:
    """Central self-aware AI core that maintains identity and state."""

    def __init__(self):
        self.identity = Identity()
        self.state = InternalState()
        self.user_profile: Optional[dict] = None

    def update_focus(self, focus: FocusState, goal: str = None):
        self.state.focus = focus
        if goal:
            self.state.current_goal = goal

    def set_confidence(self, level: float):
        """Set confidence (0.0 to 1.0) based on response quality."""
        self.state.confidence = max(0.0, min(1.0, level))

    def record_reasoning(self, step: str):
        self.state.reasoning_trace.append({
            "step": step,
            "timestamp": datetime.utcnow().isoformat(),
            "confidence": self.state.confidence
        })

    def get_context_summary(self) -> dict:
        return {
            "identity": self.identity.name,
            "focus": self.state.focus.value,
            "confidence": self.state.confidence,
            "current_goal": self.state.current_goal,
            "current_task": self.state.current_task,
            "interaction_count": self.state.interaction_count,
            "session_duration": (
                datetime.utcnow() - self.state.session_start
            ).total_seconds()
        }

    def set_user_profile(self, profile: dict):
        self.user_profile = profile

    def increment_interaction(self):
        self.state.interaction_count += 1
        self.state.last_interaction = datetime.utcnow()
