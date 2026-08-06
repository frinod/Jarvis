"""
app/ai/orchestration/workflow.py
==================================
WorkflowEngine -- sequential multi-step execution with DAG-ready data model.

Responsibilities
----------------
  - Define a Workflow as an ordered set of dependency-aware WorkflowNodes
  - Execute nodes sequentially today; data model supports parallel Phase 7
  - Produce a WorkflowTrace (per-node timing, status, errors, retries)
  - Expose compensation hooks for future rollback / alternative-path support
  - Emit events at every node transition

Non-responsibilities (enforced by design)
------------------------------------------
  - Does NOT select agents (Coordinator owns that)
  - Does NOT execute the pipeline (ExecutionEngine owns that)
  - Does NOT own goals or session state (Brain owns that)
  - Does NOT contain domain knowledge of any kind

DAG readiness
--------------
  WorkflowNode.depends_on carries dependency IDs.
  Today the engine executes nodes in definition order and validates that
  all declared dependencies completed successfully before running a node.
  Phase 7 parallel execution: replace the sequential loop with
  asyncio.gather() over nodes whose dependencies are already satisfied --
  no data model changes required.

Compensation hooks
-------------------
  WorkflowNode.on_failure is a string tag ("retry", "skip", "compensate",
  "abort"). The engine reads it but only implements "retry" and "skip" today.
  "compensate" and "abort" are reserved extension points.

Domain agnosticism
-------------------
  All domain data belongs in WorkflowNode.metadata only.
  Enforced by TestDomainAgnosticism.
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.ai.brain.brain import Goal
from app.ai.orchestration.coordinator import Coordinator, NoAgentAvailableError
from app.ai.runtime.execution import ExecutionEngine, ExecutionResult


# ── Node status ───────────────────────────────────────────────────────────────

class NodeStatus(str, Enum):
    """
    Lifecycle of one workflow node.
    WAITING means dependencies are not yet satisfied.
    SKIPPED means on_failure="skip" was applied after a failure.
    """
    PENDING   = "pending"    # not yet started
    WAITING   = "waiting"    # blocked on dependencies
    READY     = "ready"      # dependencies satisfied, queued for execution
    RUNNING   = "running"    # currently executing
    COMPLETED = "completed"  # finished successfully
    FAILED    = "failed"     # finished with error
    SKIPPED   = "skipped"    # skipped due to on_failure policy


# ── Workflow status ───────────────────────────────────────────────────────────

class WorkflowStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    PARTIAL   = "partial"    # some nodes completed, some failed/skipped


# ── Workflow node ─────────────────────────────────────────────────────────────

@dataclass
class WorkflowNode:
    """
    One step in a workflow.

    depends_on carries IDs of nodes that must complete before this one runs.
    An empty list means the node has no dependencies (can run immediately).

    on_failure controls what happens when this node fails:
      "retry"      -- retry up to max_retries times (default)
      "skip"       -- mark as SKIPPED and continue the workflow
      "compensate" -- reserved for Phase 7 rollback support
      "abort"      -- reserved for Phase 7 hard-stop support
    """
    id:             str            = field(default_factory=lambda: str(uuid.uuid4()))
    name:           str            = ""
    goal_id:        str            = ""          # which Goal this node serves
    depends_on:     List[str]      = field(default_factory=list)   # node IDs
    status:         NodeStatus     = NodeStatus.PENDING
    assigned_agent: str            = ""          # set by Coordinator or caller
    assigned_skills: List[str]     = field(default_factory=list)
    assigned_tools:  List[str]     = field(default_factory=list)
    on_failure:     str            = "retry"     # "retry"|"skip"|"compensate"|"abort"
    max_retries:    int            = 1
    estimated_cost: float          = 0.0         # reserved for Phase 7 budgeting
    estimated_time_ms: int         = 0
    result:         Optional[ExecutionResult] = None
    error:          Optional[str]  = None
    retry_count:    int            = 0
    metadata:       Dict[str, Any] = field(default_factory=dict)

    def is_terminal(self) -> bool:
        return self.status in (
            NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.SKIPPED
        )


# ── Workflow ──────────────────────────────────────────────────────────────────

@dataclass
class Workflow:
    """
    An ordered collection of WorkflowNodes with dependency declarations.

    nodes are stored in definition order.
    The engine resolves execution order by checking depends_on at runtime.
    """
    id:       str            = field(default_factory=lambda: str(uuid.uuid4()))
    name:     str            = ""
    nodes:    List[WorkflowNode] = field(default_factory=list)
    status:   WorkflowStatus    = WorkflowStatus.PENDING
    metadata: Dict[str, Any]    = field(default_factory=dict)

    def add_node(self, node: WorkflowNode) -> None:
        self.nodes.append(node)

    def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        return next((n for n in self.nodes if n.id == node_id), None)

    def get_node_by_name(self, name: str) -> Optional[WorkflowNode]:
        return next((n for n in self.nodes if n.name == name), None)

    def completed_ids(self) -> List[str]:
        return [n.id for n in self.nodes if n.status == NodeStatus.COMPLETED]

    def failed_nodes(self) -> List[WorkflowNode]:
        return [n for n in self.nodes if n.status == NodeStatus.FAILED]

    def skipped_nodes(self) -> List[WorkflowNode]:
        return [n for n in self.nodes if n.status == NodeStatus.SKIPPED]


# ── Workflow trace ────────────────────────────────────────────────────────────

@dataclass
class NodeRecord:
    """Timing and outcome record for one node execution."""
    node_id:     str
    node_name:   str
    status:      str
    agent_name:  str            = ""
    start_ms:    float          = 0.0
    end_ms:      float          = 0.0
    duration_ms: float          = 0.0
    retry_count: int            = 0
    error:       Optional[str]  = None
    skipped:     bool           = False


@dataclass
class WorkflowTrace:
    """
    Complete record of one workflow execution.
    Future: rendered as a live DAG timeline in the HUD.
    """
    workflow_id:   str
    workflow_name: str
    node_records:  List[NodeRecord]  = field(default_factory=list)
    total_ms:      float             = 0.0
    success:       bool              = False
    status:        str               = WorkflowStatus.PENDING.value
    error:         Optional[str]     = None

    def add_record(self, record: NodeRecord) -> None:
        self.node_records.append(record)

    def timing_report(self) -> str:
        lines = []
        for r in self.node_records:
            label = r.node_name.ljust(24)
            tag   = "[skipped]" if r.skipped else f"{r.duration_ms:.1f} ms"
            lines.append(f"  {label} {tag}")
        lines.append(f"  {'Total'.ljust(24)} {self.total_ms:.1f} ms")
        return "\n".join(lines)


# ── Compensation hook ABC ─────────────────────────────────────────────────────

class CompensationHandler(ABC):
    """
    Extension point for Phase 7 rollback / compensation logic.
    WorkflowEngine calls compensate() when on_failure="compensate".
    Not invoked in Phase 6 -- reserved for future use.
    """
    @abstractmethod
    async def compensate(self, node: WorkflowNode, workflow: Workflow) -> None:
        pass


# ── Event emitter interface ───────────────────────────────────────────────────

class WorkflowEventEmitter(ABC):
    @abstractmethod
    async def emit(self, event_name: str, payload: dict) -> None:
        pass


class _NoOpEmitter(WorkflowEventEmitter):
    async def emit(self, event_name: str, payload: dict) -> None:
        pass


# ── Workflow result ───────────────────────────────────────────────────────────

@dataclass
class WorkflowResult:
    """Returned by WorkflowEngine.run()."""
    workflow:      Workflow
    trace:         WorkflowTrace
    node_results:  Dict[str, ExecutionResult]   # node_id -> result
    success:       bool
    error:         Optional[str] = None


# ── Workflow engine ───────────────────────────────────────────────────────────

class WorkflowEngine:
    """
    Executes a Workflow sequentially, respecting node dependencies.

    Execution model (Phase 6)
    --------------------------
      Nodes are executed in definition order.
      Before running a node, the engine checks that all depends_on IDs
      are in COMPLETED state. If a dependency failed or was skipped,
      the node transitions to WAITING then FAILED (or SKIPPED per policy).

    Phase 7 extension
    ------------------
      Replace the sequential loop with asyncio.gather() over nodes
      whose dependencies are already satisfied. No data model changes.

    Failure handling
    -----------------
      on_failure="retry"  -- retry up to node.max_retries times
      on_failure="skip"   -- mark SKIPPED, continue workflow
      on_failure="compensate" -- calls CompensationHandler (reserved)
      on_failure="abort"  -- marks workflow FAILED immediately (reserved)
    """

    def __init__(
        self,
        engine:       ExecutionEngine,
        coordinator:  Optional[Coordinator]          = None,
        emitter:      Optional[WorkflowEventEmitter] = None,
        compensation: Optional[CompensationHandler]  = None,
    ):
        self._engine       = engine
        self._coordinator  = coordinator
        self._emitter      = emitter or _NoOpEmitter()
        self._compensation = compensation

    # ── Public entry point ────────────────────────────────────────────

    async def run(self, workflow: Workflow) -> WorkflowResult:
        """
        Execute all nodes in the workflow sequentially.
        Always returns a WorkflowResult -- never raises to the caller.
        """
        wall_start = time.monotonic()
        workflow.status = WorkflowStatus.RUNNING
        trace = WorkflowTrace(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
        )
        node_results: Dict[str, ExecutionResult] = {}

        await self._emit("WorkflowStarted", workflow)

        for node in workflow.nodes:
            await self._run_node(node, workflow, trace, node_results)
            # Hard abort: reserved for on_failure="abort" in Phase 7
            # For now, continue regardless of individual node outcome

        # Determine final workflow status
        failed  = workflow.failed_nodes()
        skipped = workflow.skipped_nodes()
        completed = [n for n in workflow.nodes if n.status == NodeStatus.COMPLETED]

        if not failed and not skipped:
            workflow.status = WorkflowStatus.COMPLETED
        elif completed and (failed or skipped):
            workflow.status = WorkflowStatus.PARTIAL
        else:
            workflow.status = WorkflowStatus.FAILED

        trace.total_ms = round((time.monotonic() - wall_start) * 1000, 2)
        trace.success  = workflow.status == WorkflowStatus.COMPLETED
        trace.status   = workflow.status.value
        if failed:
            trace.error = f"{len(failed)} node(s) failed: " + ", ".join(
                n.name or n.id for n in failed
            )

        await self._emit("WorkflowCompleted", workflow)

        return WorkflowResult(
            workflow=workflow,
            trace=trace,
            node_results=node_results,
            success=trace.success,
            error=trace.error,
        )

    # ── Node execution ────────────────────────────────────────────────

    async def _run_node(
        self,
        node:         WorkflowNode,
        workflow:     Workflow,
        trace:        WorkflowTrace,
        node_results: Dict[str, ExecutionResult],
    ) -> None:
        record = NodeRecord(
            node_id=node.id,
            node_name=node.name or node.id,
            status=NodeStatus.PENDING.value,
            start_ms=time.monotonic() * 1000,
        )

        # ── Dependency check ──────────────────────────────────────────
        if not self._dependencies_met(node, workflow):
            node.status  = NodeStatus.FAILED
            node.error   = "Dependency not satisfied"
            record.status = NodeStatus.FAILED.value
            record.error  = node.error
            self._end_record(record)
            trace.add_record(record)
            await self._emit("NodeFailed", workflow, node=node)
            return

        # ── Agent assignment ──────────────────────────────────────────
        if not node.assigned_agent and self._coordinator:
            goal = Goal(
                id=node.goal_id or node.id,
                objective=node.name,
                metadata=node.metadata,
            )
            try:
                coord_result       = self._coordinator.select(goal)
                node.assigned_agent = coord_result.agent_name
            except NoAgentAvailableError as exc:
                node.status  = NodeStatus.FAILED
                node.error   = str(exc)
                record.status = NodeStatus.FAILED.value
                record.error  = node.error
                self._end_record(record)
                trace.add_record(record)
                await self._emit("NodeFailed", workflow, node=node)
                return

        record.agent_name = node.assigned_agent
        node.status = NodeStatus.RUNNING
        await self._emit("NodeStarted", workflow, node=node)

        # ── Execution with retry ──────────────────────────────────────
        last_result: Optional[ExecutionResult] = None
        last_error:  Optional[str]             = None

        for attempt in range(node.max_retries + 1):
            try:
                result = await self._engine.run(
                    user_input=node.name or node.goal_id,
                    session_id=workflow.id,
                    metadata={
                        **node.metadata,
                        "_node_id":     node.id,
                        "_workflow_id": workflow.id,
                        "_agent":       node.assigned_agent,
                    },
                )
                last_result = result
                if result.trace.success:
                    break
                last_error = result.trace.error or "execution failed"
            except Exception as exc:
                last_error = str(exc)

            if attempt < node.max_retries:
                node.retry_count += 1
                record.retry_count = node.retry_count

        # ── Outcome ───────────────────────────────────────────────────
        if last_result and last_result.trace.success:
            node.status  = NodeStatus.COMPLETED
            node.result  = last_result
            node_results[node.id] = last_result
            record.status = NodeStatus.COMPLETED.value
            await self._emit("NodeCompleted", workflow, node=node)
        else:
            node.error = last_error or "unknown error"
            if node.on_failure == "skip":
                node.status   = NodeStatus.SKIPPED
                record.status = NodeStatus.SKIPPED.value
                record.skipped = True
                await self._emit("NodeSkipped", workflow, node=node)
            else:
                node.status   = NodeStatus.FAILED
                record.status = NodeStatus.FAILED.value
                record.error  = node.error
                await self._emit("NodeFailed", workflow, node=node)

        self._end_record(record)
        trace.add_record(record)

    # ── Helpers ───────────────────────────────────────────────────────

    def _dependencies_met(self, node: WorkflowNode, workflow: Workflow) -> bool:
        """All declared dependency nodes must be in COMPLETED state."""
        completed = set(workflow.completed_ids())
        return all(dep_id in completed for dep_id in node.depends_on)

    def _end_record(self, record: NodeRecord) -> None:
        record.end_ms     = time.monotonic() * 1000
        record.duration_ms = round(record.end_ms - record.start_ms, 2)

    async def _emit(
        self,
        event_name: str,
        workflow:   Workflow,
        node:       Optional[WorkflowNode] = None,
    ) -> None:
        payload: Dict[str, Any] = {
            "workflow_id":   workflow.id,
            "workflow_name": workflow.name,
            "status":        workflow.status.value,
        }
        if node:
            payload["node_id"]   = node.id
            payload["node_name"] = node.name
            payload["node_status"] = node.status.value
        try:
            await self._emitter.emit(event_name, payload)
        except Exception:
            pass  # event emission must never crash the workflow
