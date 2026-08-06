"""
app/ai/runtime/execution.py
============================
ExecutionEngine -- the Thinking Pipeline orchestrator.

Responsibilities
----------------
  - Drive ExecutionContext through every pipeline stage in order
  - Emit an event to the EventBus at each state transition
  - Record an ExecutionTrace (per-stage timing, events, errors, retries)
  - Coordinate injected collaborators: Planner, MemoryProvider,
    SkillRunner, ToolRunner, Reasoner, Verifier, Responder
  - Handle stage failures gracefully (partial-info continuation vs abort)
  - Populate ExecutionContext.timings at every stage

Non-responsibilities (enforced by design)
------------------------------------------
  - Does NOT contain business logic of any kind
  - Does NOT know what any skill, tool, or agent does
  - Does NOT know about trading, stocks, or any domain
  - Does NOT build prompts -- Responder does that

Collaborator interfaces
------------------------
  All collaborators are injected as ABCs.
  Tests inject mocks. Real implementations plug in later.
  This means the engine is fully testable today even though
  Brain, Memory, and Agents are not yet implemented.

Parallel execution readiness
------------------------------
  Each stage method is async. The engine calls them sequentially today.
  To parallelise stages (e.g. memory + tools simultaneously), replace
  sequential awaits with asyncio.gather() -- no interface changes needed.

ExecutionTrace
---------------
  Accumulates a structured record of every stage: start/end time,
  duration, events emitted, tools used, skills used, errors, retries.
  Returned alongside the final response for debugging and HUD display.
"""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.ai.runtime.context import ExecutionContext, RequestState
from app.ai.runtime.llm_gateway import LLMGateway, LLMRequest, LLMResponse
from app.core.llm import LLMMessage


# ── Trace ─────────────────────────────────────────────────────────────────────

@dataclass
class StageRecord:
    """Timing and event record for one pipeline stage."""
    stage:        str
    start_ms:     float
    end_ms:       float = 0.0
    duration_ms:  float = 0.0
    events:       List[str] = field(default_factory=list)
    error:        Optional[str] = None
    skipped:      bool = False


@dataclass
class ExecutionTrace:
    """
    Complete record of one request's journey through the pipeline.
    Returned by ExecutionEngine.run() alongside the response.
    Future: visualised as a live timeline in the HUD.
    """
    request_id:    str
    session_id:    str
    stages:        List[StageRecord] = field(default_factory=list)
    tools_used:    List[str]         = field(default_factory=list)
    skills_used:   List[str]         = field(default_factory=list)
    agent_name:    str               = ""
    total_ms:      float             = 0.0
    success:       bool              = False
    error:         Optional[str]     = None
    retry_count:   int               = 0

    def add_stage(self, record: StageRecord) -> None:
        self.stages.append(record)

    def timing_report(self) -> str:
        """Human-readable timing breakdown for logging."""
        lines = []
        for s in self.stages:
            label = f"{s.stage}".ljust(20)
            if s.skipped:
                lines.append(f"  {label} [skipped]")
            else:
                lines.append(f"  {label} {s.duration_ms:.1f} ms")
        lines.append(f"  {'Total'.ljust(20)} {self.total_ms:.1f} ms")
        return "\n".join(lines)


# ── Collaborator interfaces ───────────────────────────────────────────────────

class PipelinePlanner(ABC):
    """
    Understands the request and produces a plan.
    Sets: ctx.intent_type, ctx.active_goal, ctx.selected_agent.
    """
    @abstractmethod
    async def plan(self, ctx: ExecutionContext) -> None:
        pass


class PipelineMemoryProvider(ABC):
    """
    Retrieves relevant memories and injects them into the context.
    Sets: ctx.memory_context.
    """
    @abstractmethod
    async def load(self, ctx: ExecutionContext) -> None:
        pass


class PipelineSkillRunner(ABC):
    """
    Selects and executes skills appropriate for the current context.
    Sets: ctx.skill_results.
    """
    @abstractmethod
    async def run(self, ctx: ExecutionContext) -> None:
        pass


class PipelineToolRunner(ABC):
    """
    Executes tools required by the plan.
    Sets: ctx.tool_results.
    """
    @abstractmethod
    async def run(self, ctx: ExecutionContext) -> None:
        pass


class PipelineReasoner(ABC):
    """
    Runs chain-of-thought reasoning over the assembled context.
    Sets: ctx.thought_chain, ctx.confidence.
    """
    @abstractmethod
    async def reason(self, ctx: ExecutionContext) -> None:
        pass


class PipelineVerifier(ABC):
    """
    Verifies the reasoning output and decides whether to retry.
    Sets: ctx.critique. Returns True if reasoning should be retried.
    """
    @abstractmethod
    async def verify(self, ctx: ExecutionContext) -> bool:
        pass


class PipelineResponder(ABC):
    """
    Assembles the final response using the LLM gateway.
    Sets: ctx.response, ctx.explanation.
    """
    @abstractmethod
    async def respond(self, ctx: ExecutionContext) -> None:
        pass


# ── Event emitter interface ───────────────────────────────────────────────────

class ExecutionEventEmitter(ABC):
    """
    Thin wrapper around EventBus for the execution engine.
    Decouples the engine from the concrete EventBus implementation.
    """
    @abstractmethod
    async def emit(self, event_name: str, payload: dict) -> None:
        pass


class _NoOpEmitter(ExecutionEventEmitter):
    async def emit(self, event_name: str, payload: dict) -> None:
        pass


# ── Execution result ──────────────────────────────────────────────────────────

@dataclass
class ExecutionResult:
    """Returned by ExecutionEngine.run()."""
    response:    str
    confidence:  float
    explanation: str
    trace:       ExecutionTrace
    context:     ExecutionContext


# ── Engine ────────────────────────────────────────────────────────────────────

class ExecutionEngine:
    """
    Drives the Thinking Pipeline for one AI request.

    All collaborators are injected. The engine itself contains no
    business logic -- it only orchestrates transitions and timing.

    Usage
    -----
        engine = ExecutionEngine(
            gateway=gateway,
            planner=planner,
            memory=memory,
            skill_runner=skill_runner,
            tool_runner=tool_runner,
            reasoner=reasoner,
            verifier=verifier,
            responder=responder,
        )
        result = await engine.run(user_input, session_id)
    """

    MAX_REASONING_RETRIES = 2

    def __init__(
        self,
        gateway:      LLMGateway,
        planner:      Optional[PipelinePlanner]       = None,
        memory:       Optional[PipelineMemoryProvider] = None,
        skill_runner: Optional[PipelineSkillRunner]   = None,
        tool_runner:  Optional[PipelineToolRunner]    = None,
        reasoner:     Optional[PipelineReasoner]      = None,
        verifier:     Optional[PipelineVerifier]      = None,
        responder:    Optional[PipelineResponder]     = None,
        emitter:      Optional[ExecutionEventEmitter] = None,
        cancel_event: Optional[asyncio.Event]         = None,
    ):
        self._gateway      = gateway
        self._planner      = planner
        self._memory       = memory
        self._skill_runner = skill_runner
        self._tool_runner  = tool_runner
        self._reasoner     = reasoner
        self._verifier     = verifier
        self._responder    = responder
        self._emitter      = emitter or _NoOpEmitter()
        self._cancel_event = cancel_event

    # ── Public entry point ────────────────────────────────────────────

    async def run(
        self,
        user_input:  str,
        session_id:  str = "",
        history:     Optional[list] = None,
        metadata:    Optional[dict] = None,
    ) -> ExecutionResult:
        """
        Execute the full Thinking Pipeline for one request.
        Always returns an ExecutionResult -- never raises to the caller.
        Failures are captured in ExecutionResult.trace.error.
        """
        ctx = ExecutionContext(
            session_id=session_id,
            user_input=user_input,
            metadata=metadata or {},
        )
        if history:
            ctx.history = history

        trace = ExecutionTrace(
            request_id=ctx.request_id,
            session_id=session_id,
        )
        wall_start = time.monotonic()

        await self._emit("RequestStarted", ctx)

        # ── Pipeline stages ───────────────────────────────────────────
        await self._stage_plan(ctx, trace)
        if not ctx.is_failed():
            await self._stage_memory(ctx, trace)
        if not ctx.is_failed():
            await self._stage_skills(ctx, trace)
        if not ctx.is_failed():
            await self._stage_tools(ctx, trace)
        if not ctx.is_failed():
            await self._stage_reason(ctx, trace)
        if not ctx.is_failed():
            await self._stage_respond(ctx, trace)

        # ── Finalise ──────────────────────────────────────────────────
        trace.total_ms    = round((time.monotonic() - wall_start) * 1000, 2)
        trace.agent_name  = ctx.selected_agent
        trace.retry_count = ctx.retry_count
        trace.tools_used  = list(ctx.tool_results.keys())
        trace.skills_used = list(ctx.skill_results.keys())

        if ctx.is_failed():
            trace.success = False
            trace.error   = ctx.error
            ctx.transition(RequestState.FAILED)
            await self._emit("RequestFinished", ctx, success=False)
        else:
            trace.success = True
            ctx.transition(RequestState.COMPLETED)
            await self._emit("RequestFinished", ctx, success=True)

        return ExecutionResult(
            response    = ctx.response or "",
            confidence  = ctx.confidence,
            explanation = ctx.explanation,
            trace       = trace,
            context     = ctx,
        )

    # ── Stage: Planning ───────────────────────────────────────────────

    async def _stage_plan(self, ctx: ExecutionContext, trace: ExecutionTrace) -> None:
        record = self._start_record("planning")
        ctx.transition(RequestState.PLANNING)
        await self._emit("PlanningStarted", ctx)
        try:
            if self._planner:
                await self._planner.plan(ctx)
            else:
                # Default: use raw user_input as goal
                ctx.active_goal = ctx.user_input
                ctx.intent_type = "general"
            await self._emit("PlanningCompleted", ctx)
        except Exception as exc:
            ctx.fail(f"Planning failed: {exc}")
            record.error = str(exc)
        self._end_record(record)
        trace.add_stage(record)

    # ── Stage: Memory ─────────────────────────────────────────────────

    async def _stage_memory(self, ctx: ExecutionContext, trace: ExecutionTrace) -> None:
        record = self._start_record("memory_loading")
        ctx.transition(RequestState.MEMORY_LOADING)
        await self._emit("MemoryLoadStarted", ctx)
        try:
            if self._memory:
                await self._memory.load(ctx)
            # No memory provider: continue with empty memory_context
            await self._emit("MemoryLoaded", ctx)
        except Exception as exc:
            # Memory failure is non-fatal: log and continue
            record.error = f"Memory load failed (continuing): {exc}"
        self._end_record(record)
        trace.add_stage(record)

    # ── Stage: Skills ─────────────────────────────────────────────────

    async def _stage_skills(self, ctx: ExecutionContext, trace: ExecutionTrace) -> None:
        record = self._start_record("skill_selection")
        ctx.transition(RequestState.SKILL_SELECTION)
        try:
            if self._skill_runner:
                await self._skill_runner.run(ctx)
            await self._emit("SkillsExecuted", ctx)
        except Exception as exc:
            # Skill failure is non-fatal: reasoning continues with partial results
            record.error = f"Skill execution failed (continuing): {exc}"
        self._end_record(record)
        trace.add_stage(record)

    # ── Stage: Tools ──────────────────────────────────────────────────

    async def _stage_tools(self, ctx: ExecutionContext, trace: ExecutionTrace) -> None:
        record = self._start_record("tool_execution")
        ctx.transition(RequestState.TOOL_EXECUTION)
        try:
            if self._tool_runner:
                await self._tool_runner.run(ctx)
            await self._emit("ToolsExecuted", ctx)
        except Exception as exc:
            # Tool failure is non-fatal: reasoning continues with partial results
            record.error = f"Tool execution failed (continuing): {exc}"
        self._end_record(record)
        trace.add_stage(record)

    # ── Stage: Reasoning (with retry) ────────────────────────────────

    async def _stage_reason(self, ctx: ExecutionContext, trace: ExecutionTrace) -> None:
        record = self._start_record("reasoning")
        ctx.transition(RequestState.REASONING)
        await self._emit("ReasoningStarted", ctx)
        try:
            for attempt in range(self.MAX_REASONING_RETRIES + 1):
                if self._reasoner:
                    await self._reasoner.reason(ctx)

                # Verification
                should_retry = False
                if self._verifier:
                    ctx.transition(RequestState.VERIFICATION)
                    await self._emit("VerificationStarted", ctx)
                    should_retry = await self._verifier.verify(ctx)
                    await self._emit("VerificationCompleted", ctx)
                    ctx.transition(RequestState.REASONING)

                if not should_retry or attempt >= self.MAX_REASONING_RETRIES:
                    break

                ctx.retry_count += 1
                record.events.append(f"retry_{ctx.retry_count}")

            await self._emit("ReasoningCompleted", ctx)
        except Exception as exc:
            ctx.fail(f"Reasoning failed: {exc}")
            record.error = str(exc)
        self._end_record(record)
        trace.add_stage(record)

    # ── Stage: Response assembly ──────────────────────────────────────

    async def _stage_respond(self, ctx: ExecutionContext, trace: ExecutionTrace) -> None:
        record = self._start_record("response_generation")
        ctx.transition(RequestState.RESPONSE_GENERATION)
        await self._emit("ResponseStarted", ctx)
        try:
            if self._responder:
                await self._responder.respond(ctx)
            else:
                # Minimal fallback: echo goal if no responder configured
                ctx.response = ctx.active_goal or ctx.user_input
                if ctx.confidence == 0.0:
                    ctx.confidence = 0.5
            await self._emit("ResponseReady", ctx)
        except Exception as exc:
            ctx.fail(f"Response assembly failed: {exc}")
            record.error = str(exc)
        self._end_record(record)
        trace.add_stage(record)

    # ── Stream variant ────────────────────────────────────────────────

    async def stream(
        self,
        user_input:  str,
        session_id:  str = "",
        history:     Optional[list] = None,
        metadata:    Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Run the pipeline up to response assembly, then stream tokens.
        All pre-response stages (plan, memory, skills, tools, reason)
        complete before streaming begins -- streaming is response-only.
        """
        ctx = ExecutionContext(
            session_id=session_id,
            user_input=user_input,
            metadata=metadata or {},
        )
        if history:
            ctx.history = history

        trace = ExecutionTrace(request_id=ctx.request_id, session_id=session_id)

        await self._emit("RequestStarted", ctx)
        await self._stage_plan(ctx, trace)
        if not ctx.is_failed():
            await self._stage_memory(ctx, trace)
        if not ctx.is_failed():
            await self._stage_skills(ctx, trace)
        if not ctx.is_failed():
            await self._stage_tools(ctx, trace)
        if not ctx.is_failed():
            await self._stage_reason(ctx, trace)

        if ctx.is_failed():
            yield ctx.error or "Request failed"
            return

        # Build a minimal LLMRequest from context for streaming
        messages = [LLMMessage(role="user", content=ctx.active_goal or ctx.user_input)]
        req = LLMRequest(messages=messages, stream=True)
        async for token in self._gateway.stream(req, cancel_event=self._cancel_event):
            yield token

    # ── Helpers ───────────────────────────────────────────────────────

    def _start_record(self, stage: str) -> StageRecord:
        return StageRecord(stage=stage, start_ms=time.monotonic() * 1000)

    def _end_record(self, record: StageRecord) -> None:
        record.end_ms     = time.monotonic() * 1000
        record.duration_ms = round(record.end_ms - record.start_ms, 2)

    async def _emit(self, event_name: str, ctx: ExecutionContext, **extra) -> None:
        payload = {
            "request_id":     ctx.request_id,
            "session_id":     ctx.session_id,
            "state":          ctx.state.value,
            "selected_agent": ctx.selected_agent,
            **extra,
        }
        try:
            await self._emitter.emit(event_name, payload)
        except Exception:
            pass  # event emission must never crash the pipeline
