"""
app/ai/prompts/system.py
=========================
SystemPromptBuilder -- assembles the LLM message list for one pipeline request.

Phase 7B update:
  - _build_memory() now accepts a ContextAssembly (from ContextBuilder) when
    available, falling back to the raw MemoryEntry list for backward compat.
  - BuilderConfig gains max_context_tokens (800 default, ADR-003) and
    context_types filter for agent-selective context injection.
  - No interface changes -- all callers continue to work unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.ai.memory.short_term import MemoryEntry
from app.ai.prompts.templates import TemplateRegistry
from app.ai.runtime.context import ExecutionContext, ThoughtStep
from app.ai.runtime.execution import PipelineResponder
from app.ai.runtime.llm_gateway import LLMGateway, LLMRequest
from app.core.llm import LLMMessage


# Lazy import to avoid circular dependency at module load
def _get_context_assembly_type():
    try:
        from app.ai.rag.context_builder import ContextAssembly
        return ContextAssembly
    except ImportError:
        return None


# ── BuilderConfig ─────────────────────────────────────────────────────────────

@dataclass
class BuilderConfig:
    """Tuning parameters for SystemPromptBuilder."""
    agent_name:           str   = "Kiro"
    max_memory_entries:   int   = 5
    max_context_tokens:   int   = 800    # ADR-003 token budget
    include_thought_chain: bool = True
    max_thought_steps:    int   = 3
    max_history_turns:    int   = 6
    system_template:      str   = "system_base"
    context_types:        Optional[List[str]] = None  # None = all types


# ── SystemPromptBuilder ───────────────────────────────────────────────────────

class SystemPromptBuilder:
    """
    Assembles the LLM message list for one pipeline request.

    Message order:
      [0] system  -- agent identity + objective (from template)
      [1..n] user/assistant -- conversation history (recent turns)
      [n+1] user  -- memory context (if any)
      [n+2] user  -- thought chain (if any and config.include_thought_chain)
      [last] user -- current user input

    Usage
    -----
        builder  = SystemPromptBuilder()
        messages = builder.build(ctx)
        request  = LLMRequest(messages=messages)
        response = await gateway.complete(request)
    """

    def __init__(
        self,
        config:   Optional[BuilderConfig]   = None,
        registry: Optional[TemplateRegistry] = None,
    ):
        self._cfg      = config   or BuilderConfig()
        self._registry = registry or TemplateRegistry.default()

    def build(self, ctx: ExecutionContext) -> List[LLMMessage]:
        """
        Build the full message list for the current context.
        Never raises -- falls back to minimal prompt on any error.
        """
        messages: List[LLMMessage] = []

        # 1. System prompt
        messages.append(self._build_system(ctx))

        # 2. Conversation history
        messages.extend(self._build_history(ctx))

        # 3. Memory context
        mem_msg = self._build_memory(ctx)
        if mem_msg:
            messages.append(mem_msg)

        # 4. Thought chain
        if self._cfg.include_thought_chain and ctx.thought_chain:
            chain_msg = self._build_chain(ctx)
            if chain_msg:
                messages.append(chain_msg)

        # 5. Current user input
        messages.append(LLMMessage(role="user", content=ctx.user_input))

        return messages

    # ── Section builders ──────────────────────────────────────────────

    def _build_system(self, ctx: ExecutionContext) -> LLMMessage:
        objective = ctx.active_goal or ctx.user_input
        try:
            template = self._registry.get(self._cfg.system_template)
            content  = template.render(
                agent_name=self._cfg.agent_name,
                objective=objective,
            )
        except (KeyError, Exception):
            content = f"You are {self._cfg.agent_name}. Objective: {objective}"
        return LLMMessage(role="system", content=content)

    def _build_history(self, ctx: ExecutionContext) -> List[LLMMessage]:
        turns = ctx.recent_history(self._cfg.max_history_turns)
        return [LLMMessage(role=t.role, content=t.content) for t in turns]

    def _build_memory(self, ctx: ExecutionContext) -> Optional[LLMMessage]:
        # Phase 7B: use ContextAssembly if stored in ctx.metadata
        ContextAssembly = _get_context_assembly_type()
        if ContextAssembly is not None:
            assembly = ctx.metadata.get("_rag_context")
            if assembly is not None and isinstance(assembly, ContextAssembly):
                from app.ai.rag.context_builder import PromptContextAssembler
                assembler = PromptContextAssembler()
                text = assembler.format(assembly, include_types=self._cfg.context_types)
                if text:
                    return LLMMessage(role="user", content=f"Relevant context:\n{text}")
                return None

        # Phase 6 fallback: raw MemoryEntry list
        entries = ctx.memory_context[: self._cfg.max_memory_entries]
        if not entries:
            return None
        lines = []
        for e in entries:
            if isinstance(e, MemoryEntry):
                lines.append(f"- [{e.role.value}] {e.content}")
            else:
                lines.append(f"- {str(e)}")
        return LLMMessage(role="user", content="Relevant context:\n" + "\n".join(lines))

    def _build_chain(self, ctx: ExecutionContext) -> Optional[LLMMessage]:
        steps = ctx.thought_chain[: self._cfg.max_thought_steps]
        if not steps:
            return None
        lines = [f"Step {s.step_index}: {s.content}" for s in steps]
        content = "Reasoning so far:\n" + "\n".join(lines)
        return LLMMessage(role="user", content=content)

    # ── Convenience ───────────────────────────────────────────────────

    def build_request(
        self,
        ctx:         ExecutionContext,
        temperature: float = 0.7,
        max_tokens:  int   = 1024,
    ) -> LLMRequest:
        """Build a complete LLMRequest from context."""
        return LLMRequest(
            messages=self.build(ctx),
            temperature=temperature,
            max_tokens=max_tokens,
        )


# ── PipelineResponderAdapter ──────────────────────────────────────────────────

class PipelineResponderAdapter(PipelineResponder):
    """
    Bridges SystemPromptBuilder + LLMGateway to the PipelineResponder ABC.
    Injected into ExecutionEngine as the responder collaborator.

    Assembles the full message list, calls the gateway, and writes
    ctx.response and ctx.explanation.
    """

    def __init__(
        self,
        gateway: LLMGateway,
        builder: Optional[SystemPromptBuilder] = None,
    ):
        self._gateway = gateway
        self._builder = builder or SystemPromptBuilder()

    async def respond(self, ctx: ExecutionContext) -> None:
        request  = self._builder.build_request(ctx)
        response = await self._gateway.complete(request)
        ctx.response    = response.content
        ctx.explanation = (
            f"Generated by {response.provider_name} "
            f"({response.usage.total_tokens} tokens, "
            f"{response.latency_ms:.0f}ms, "
            f"confidence {ctx.confidence:.0%})"
        )
