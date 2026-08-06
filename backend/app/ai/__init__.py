"""
app/ai/__init__.py
==================
AIRuntime -- the single public entry point for the JARVIS AI Cognition Runtime.

This facade wires together every Phase 6A component:

    User
      │
      ▼
    AIRuntime.process()          ← single-turn request
    AIRuntime.stream()           ← streaming single-turn request
    AIRuntime.run_workflow()     ← multi-step workflow request
      │
      ▼
    Brain                        ← goal creation, confidence, reflection
      │
      ▼
    Coordinator                  ← capability-based agent selection
      │
      ▼
    ExecutionEngine              ← Thinking Pipeline orchestration
      │
      ▼
    LLMGateway                   ← provider-agnostic LLM execution

The existing JarvisOrchestrator in app/core/orchestrator.py remains the
API entry point and will delegate to AIRuntime once Phase 6 is wired.
This facade is NOT deleted or replaced -- it is the target of that delegation.

Responsibilities
----------------
  - Construct and own all Phase 6A components
  - Expose process(), stream(), run_workflow() as the public API
  - Expose health() and metrics() for observability
  - Accept a DIContainer for kernel integration (optional in Phase 6A)

Non-responsibilities
---------------------
  - Does NOT contain business logic
  - Does NOT know about trading, stocks, or any domain
  - Does NOT duplicate any component's internal logic

Domain agnosticism
-------------------
  All domain data travels through metadata dicts only.
  Enforced by TestDomainAgnosticism.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.ai.brain.brain import (
    Brain,
    BrainCapabilities,
    BrainAgentSelector,
    BrainMemoryScope,
    BrainExecutionPolicy,
)
from app.ai.orchestration.coordinator import (
    AgentDescriptor,
    AgentRegistry,
    Coordinator,
    CoordinatorAgentSelector,
)
from app.ai.orchestration.workflow import (
    Workflow,
    WorkflowEngine,
    WorkflowResult,
)
from app.ai.runtime.execution import ExecutionEngine, ExecutionResult
from app.ai.runtime.llm_gateway import LLMGateway


# ── Runtime health snapshot ───────────────────────────────────────────────────

@dataclass
class RuntimeHealth:
    """Point-in-time health snapshot of the AIRuntime."""
    status:          str                  # "healthy" | "degraded" | "offline"
    registered_agents: List[str]          = field(default_factory=list)
    healthy_agents:    List[str]          = field(default_factory=list)
    gateway_providers: List[str]          = field(default_factory=list)
    details:           Dict[str, Any]     = field(default_factory=dict)


# ── Runtime metrics snapshot ──────────────────────────────────────────────────

@dataclass
class RuntimeMetrics:
    """Lightweight metrics snapshot. Full metrics live in MetricsEngine (Phase 6 wiring)."""
    total_requests:    int   = 0
    total_workflows:   int   = 0
    active_goals:      int   = 0
    completed_goals:   int   = 0
    failed_goals:      int   = 0
    total_decisions:   int   = 0
    total_reflections: int   = 0


# ── AIRuntime ─────────────────────────────────────────────────────────────────

class AIRuntime:
    """
    Single public entry point for the JARVIS AI Cognition Runtime.

    Minimal construction
    --------------------
        gateway = LLMGateway(...)
        gateway.register("gemini", GeminiProvider(...))
        runtime = AIRuntime(gateway=gateway)
        result  = await runtime.process("What should I focus on today?", "sess-1")

    Full construction (with coordinator)
    -------------------------------------
        registry = AgentRegistry()
        registry.register(AgentDescriptor(name="analyst", ...))
        coordinator = Coordinator(registry=registry)
        runtime = AIRuntime(gateway=gateway, coordinator=coordinator)

    Kernel integration (Phase 6 wiring)
    -------------------------------------
        runtime = AIRuntime.from_container(di_container)
    """

    def __init__(
        self,
        gateway:          LLMGateway,
        coordinator:      Optional[Coordinator]          = None,
        agent_selector:   Optional[BrainAgentSelector]   = None,
        memory_scope:     Optional[BrainMemoryScope]     = None,
        execution_policy: Optional[BrainExecutionPolicy] = None,
        capabilities:     Optional[BrainCapabilities]    = None,
    ):
        self._gateway     = gateway
        self._coordinator = coordinator

        # Build ExecutionEngine
        self._engine = ExecutionEngine(gateway=gateway)

        # Build Coordinator bridge if coordinator provided
        selector = agent_selector
        if coordinator is not None and agent_selector is None:
            selector = CoordinatorAgentSelector(coordinator)

        # Build Brain
        self._brain = Brain(
            engine=self._engine,
            agent_selector=selector,
            memory_scope=memory_scope,
            execution_policy=execution_policy,
            capabilities=capabilities or BrainCapabilities(),
        )

        # Build WorkflowEngine
        self._workflow_engine = WorkflowEngine(
            engine=self._engine,
            coordinator=coordinator,
        )

        self._request_count  = 0
        self._workflow_count = 0

    # ── Core API ──────────────────────────────────────────────────────

    async def process(
        self,
        user_input: str,
        session_id: str = "",
        metadata:   Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Process one user request through the full Thinking Pipeline.
        Routes through Brain → Coordinator → ExecutionEngine.
        Always returns an ExecutionResult -- never raises to the caller.
        """
        self._request_count += 1
        return await self._brain.process(
            user_input=user_input,
            session_id=session_id,
            metadata=metadata,
        )

    async def stream(
        self,
        user_input: str,
        session_id: str = "",
        metadata:   Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a response token-by-token.
        All pre-response pipeline stages complete before streaming begins.
        """
        self._request_count += 1
        async for token in self._engine.stream(
            user_input=user_input,
            session_id=session_id,
            metadata=metadata,
        ):
            yield token

    async def run_workflow(self, workflow: Workflow) -> WorkflowResult:
        """
        Execute a multi-step Workflow through the WorkflowEngine.
        Nodes are executed sequentially with dependency validation.
        """
        self._workflow_count += 1
        return await self._workflow_engine.run(workflow)

    # ── Observability ─────────────────────────────────────────────────

    async def health(self) -> RuntimeHealth:
        """Return a point-in-time health snapshot."""
        registry = self._coordinator.registry if self._coordinator else None

        registered = registry.all_names() if registry else []
        healthy    = (
            [d.name for d in registry.available()]
            if registry else []
        )
        providers  = list(self._gateway._providers.keys())

        status = "healthy"
        if registry and not healthy:
            status = "degraded"
        if not providers:
            status = "offline"

        return RuntimeHealth(
            status=status,
            registered_agents=registered,
            healthy_agents=healthy,
            gateway_providers=providers,
            details={
                "total_requests":  self._request_count,
                "total_workflows": self._workflow_count,
            },
        )

    def metrics(self) -> RuntimeMetrics:
        """Return a lightweight metrics snapshot from Brain's session summary."""
        summary = self._brain.session_summary()
        return RuntimeMetrics(
            total_requests=self._request_count,
            total_workflows=self._workflow_count,
            active_goals=summary["active_goals"],
            completed_goals=summary["completed_goals"],
            failed_goals=summary["failed_goals"],
            total_decisions=summary["total_decisions"],
            total_reflections=summary["total_reflections"],
        )

    # ── Component accessors (for kernel wiring) ───────────────────────

    @property
    def brain(self) -> Brain:
        return self._brain

    @property
    def engine(self) -> ExecutionEngine:
        return self._engine

    @property
    def gateway(self) -> LLMGateway:
        return self._gateway

    @property
    def workflow_engine(self) -> WorkflowEngine:
        return self._workflow_engine
