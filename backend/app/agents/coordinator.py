"""JARVIS OS - Multi-Agent Architecture"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional


class AgentRole(str, Enum):
    RESEARCH = "research"
    PROGRAMMING = "programming"
    SCIENTIFIC = "scientific"
    SECURITY = "security"
    PLANNING = "planning"
    MEMORY = "memory"
    AUTOMATION = "automation"
    DATA_ANALYSIS = "data_analysis"
    CREATIVE = "creative"
    COMMUNICATION = "communication"


@dataclass
class AgentTask:
    description: str
    role: AgentRole
    context: dict
    priority: int = 5
    result: Optional[Any] = None
    status: str = "pending"


class BaseAgent(ABC):
    def __init__(self, role: AgentRole):
        self.role = role
        self.active = True

    @abstractmethod
    async def execute(self, task: AgentTask) -> Any:
        pass

    @abstractmethod
    def can_handle(self, task: AgentTask) -> bool:
        pass


class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentRole.RESEARCH)

    async def execute(self, task: AgentTask) -> Any:
        return {"agent": "research", "result": f"Researched: {task.description}"}

    def can_handle(self, task: AgentTask) -> bool:
        return task.role == AgentRole.RESEARCH


class ProgrammingAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentRole.PROGRAMMING)

    async def execute(self, task: AgentTask) -> Any:
        return {"agent": "programming", "result": f"Code task: {task.description}"}

    def can_handle(self, task: AgentTask) -> bool:
        return task.role == AgentRole.PROGRAMMING


class ScientificAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentRole.SCIENTIFIC)

    async def execute(self, task: AgentTask) -> Any:
        return {"agent": "scientific", "result": f"Scientific analysis: {task.description}"}

    def can_handle(self, task: AgentTask) -> bool:
        return task.role == AgentRole.SCIENTIFIC


class PlanningAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentRole.PLANNING)

    async def execute(self, task: AgentTask) -> Any:
        return {"agent": "planning", "result": f"Plan created: {task.description}"}

    def can_handle(self, task: AgentTask) -> bool:
        return task.role == AgentRole.PLANNING


class AgentCoordinator:
    """Routes tasks to appropriate agents and merges results."""

    def __init__(self):
        self.agents: List[BaseAgent] = [
            ResearchAgent(),
            ProgrammingAgent(),
            ScientificAgent(),
            PlanningAgent(),
        ]

    def register_agent(self, agent: BaseAgent):
        self.agents.append(agent)

    async def delegate(self, task: AgentTask) -> Any:
        for agent in self.agents:
            if agent.can_handle(task) and agent.active:
                task.status = "running"
                task.result = await agent.execute(task)
                task.status = "completed"
                return task.result
        task.status = "no_agent"
        return {"error": f"No agent available for role: {task.role}"}

    async def delegate_multi(self, tasks: List[AgentTask]) -> List[Any]:
        results = []
        for task in tasks:
            results.append(await self.delegate(task))
        return results

    def get_available_agents(self) -> List[str]:
        return [a.role.value for a in self.agents if a.active]
