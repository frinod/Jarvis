"""
app/ai/agents/__init__.py
==========================
Agents package public API.
"""
from app.ai.agents.base import BaseAgent, AgentPlan, AgentResult, VerificationResult, AgentStatus
from app.ai.agents.analyst import AnalystAgent
from app.ai.agents.researcher import ResearcherAgent
from app.ai.agents.trader import TraderAgent, TradeSignal, SignalDirection
from app.ai.agents.planner import PlannerAgent
from app.ai.agents.collaboration import AgentMessage, AgentCollaborationBus, CollaborationContext

__all__ = [
    "BaseAgent", "AgentPlan", "AgentResult", "VerificationResult", "AgentStatus",
    "AnalystAgent",
    "ResearcherAgent",
    "TraderAgent", "TradeSignal", "SignalDirection",
    "PlannerAgent",
    "AgentMessage", "AgentCollaborationBus", "CollaborationContext",
]
