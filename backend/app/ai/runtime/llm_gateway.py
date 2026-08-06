"""
app/ai/runtime/llm_gateway.py
==============================
LLMGateway -- provider-agnostic LLM execution layer.

Responsibilities
----------------
  - Accept a fully-prepared LLMRequest (prompt + params)
  - Select the correct provider (per-request override -> config default -> priority fallback)
  - Execute with retry using the Phase 5 resilience layer
  - Enforce per-request timeout and honour cancellation
  - Return a structured LLMResponse with token usage, latency, and finish reason
  - Record metrics (call count, tokens, latency, retries, errors) via callbacks
  - Support both complete and streaming response modes

Non-responsibilities (enforced by design)
------------------------------------------
  - Does NOT build prompts -- callers supply fully-prepared messages
  - Does NOT contain reasoning, planning, or domain logic
  - Does NOT know about trading, stocks, or any other domain

Provider abstraction
---------------------
  The gateway depends on app.core.llm.LLMProvider (ABC).
  Concrete providers (Gemini, Groq, Ollama, OpenAI-compatible) are registered
  by name. Switching providers requires only configuration, not code changes.
  Future providers implement LLMProvider and register -- nothing else changes.

Streaming readiness
--------------------
  complete()  -- returns full LLMResponse after generation finishes
  stream()    -- yields tokens as AsyncGenerator[str, None]
  Both share the same provider selection and retry logic.

Cancellation
-------------
  Pass an asyncio.Event as cancel_event to complete() or stream().
  The gateway checks it before each retry attempt and stops cleanly.
  This is the hook the voice interface will use to interrupt generation.

Multi-model future
-------------------
  register(name, provider, priority) supports N providers simultaneously.
  Priority-ordered fallback is built in. A future PlannedCallRouter can
  select different providers for classification vs reasoning vs summarisation
  without changing this interface.
"""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from app.core.llm import LLMProvider, LLMMessage
from app.resilience.retry import RetryPolicy, with_retry, LLM_RETRY


# ── Request / Response models ─────────────────────────────────────────────────

@dataclass
class LLMRequest:
    """
    Fully-prepared input to the gateway.
    The gateway never modifies messages -- it sends them as-is.
    """
    messages:         List[LLMMessage]
    temperature:      float = 0.7
    max_tokens:       int   = 1024
    stream:           bool  = False
    preferred_provider: Optional[str] = None   # override active provider
    timeout_s:        float = 60.0
    metadata:         Dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenUsage:
    prompt_tokens:     int = 0
    completion_tokens: int = 0
    total_tokens:      int = 0


@dataclass
class LLMResponse:
    """
    Structured output from the gateway.
    Always returned -- never a raw string.
    """
    content:       str
    provider_name: str
    model:         str
    usage:         TokenUsage
    latency_ms:    float
    finish_reason: str = "stop"
    retry_count:   int = 0
    metadata:      Dict[str, Any] = field(default_factory=dict)


# ── Provider registry entry ───────────────────────────────────────────────────

@dataclass
class _ProviderEntry:
    name:     str
    provider: LLMProvider
    priority: int   # lower = higher priority


# ── Metrics callback interface ────────────────────────────────────────────────

class GatewayMetricsCollector(ABC):
    """
    Extension point for MetricsEngine integration.
    Implement and pass to LLMGateway to record call-level metrics.
    Default no-op implementation is used when none is provided.
    """

    @abstractmethod
    def on_call_complete(self, response: LLMResponse) -> None:
        """Called after every successful complete() call."""

    @abstractmethod
    def on_call_failed(self, provider_name: str, error: str, latency_ms: float) -> None:
        """Called when all retries are exhausted."""

    @abstractmethod
    def on_stream_token(self, provider_name: str) -> None:
        """Called for each token yielded during streaming."""


class _NoOpMetrics(GatewayMetricsCollector):
    def on_call_complete(self, response: LLMResponse) -> None:
        pass

    def on_call_failed(self, provider_name: str, error: str, latency_ms: float) -> None:
        pass

    def on_stream_token(self, provider_name: str) -> None:
        pass


# ── Gateway ───────────────────────────────────────────────────────────────────

class LLMGateway:
    """
    Provider-agnostic LLM execution layer.

    Usage
    -----
        gateway = LLMGateway()
        gateway.register("gemini", GeminiProvider(...), priority=10, default=True)
        gateway.register("groq",   GroqProvider(...),   priority=20)

        response = await gateway.complete(request)
        async for token in gateway.stream(request):
            ...
    """

    def __init__(
        self,
        retry_policy:     Optional[RetryPolicy]          = None,
        metrics:          Optional[GatewayMetricsCollector] = None,
    ):
        self._providers:       Dict[str, _ProviderEntry] = {}
        self._default_name:    Optional[str]             = None
        self._retry_policy:    RetryPolicy               = retry_policy or LLM_RETRY
        self._metrics:         GatewayMetricsCollector   = metrics or _NoOpMetrics()

    # ── Registration ──────────────────────────────────────────────────

    def register(
        self,
        name:     str,
        provider: LLMProvider,
        priority: int  = 50,
        default:  bool = False,
    ) -> None:
        """Register a provider. First registered becomes default unless default=False."""
        self._providers[name] = _ProviderEntry(name=name, provider=provider, priority=priority)
        if default or self._default_name is None:
            self._default_name = name

    def set_default(self, name: str) -> None:
        if name not in self._providers:
            raise ValueError(f"Provider '{name}' not registered")
        self._default_name = name

    def registered_providers(self) -> List[str]:
        return list(self._providers.keys())

    def has_provider(self, name: str) -> bool:
        return name in self._providers

    # ── Provider selection ────────────────────────────────────────────

    def _select_provider(self, preferred: Optional[str]) -> _ProviderEntry:
        """
        Priority chain:
          1. preferred (per-request override)
          2. default (configured)
          3. highest-priority registered provider
          4. raise GatewayError
        """
        if preferred and preferred in self._providers:
            return self._providers[preferred]
        if self._default_name and self._default_name in self._providers:
            return self._providers[self._default_name]
        if self._providers:
            return min(self._providers.values(), key=lambda e: e.priority)
        raise GatewayError("No LLM providers registered")

    def _fallback_chain(self, exclude: str) -> List[_ProviderEntry]:
        """Return providers sorted by priority, excluding the named one."""
        return sorted(
            [e for e in self._providers.values() if e.name != exclude],
            key=lambda e: e.priority,
        )

    # ── Complete ──────────────────────────────────────────────────────

    async def complete(
        self,
        request:      LLMRequest,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> LLMResponse:
        """
        Execute a complete (non-streaming) LLM call.
        Retries on failure using the configured RetryPolicy.
        Falls back to next-priority provider after retries exhausted.
        Raises GatewayError if all providers fail.
        """
        entry = self._select_provider(request.preferred_provider)
        start = time.monotonic()
        retry_count = 0
        _last_exc: Exception = GatewayError("unknown")

        # Try primary provider with retry
        try:
            raw = await with_retry(
                self._retry_policy,
                self._call_provider,
                entry.provider,
                request,
                operation=f"llm.complete.{entry.name}",
                cancel_event=cancel_event,
            )
            latency_ms = (time.monotonic() - start) * 1000
            response = self._build_response(raw, entry.name, latency_ms, retry_count)
            self._metrics.on_call_complete(response)
            return response

        except Exception as exc:
            _last_exc = exc
            retry_count = self._retry_policy.max_attempts

        # Fallback chain
        for fallback in self._fallback_chain(entry.name):
            if cancel_event and cancel_event.is_set():
                raise GatewayError("Request cancelled")
            try:
                raw = await self._call_provider(fallback.provider, request)
                latency_ms = (time.monotonic() - start) * 1000
                response = self._build_response(raw, fallback.name, latency_ms, retry_count)
                self._metrics.on_call_complete(response)
                return response
            except Exception as exc:
                _last_exc = exc
                continue

        latency_ms = (time.monotonic() - start) * 1000
        self._metrics.on_call_failed(entry.name, str(_last_exc), latency_ms)
        raise GatewayError(
            f"All providers failed. Last error: {_last_exc}"
        )

    # ── Stream ────────────────────────────────────────────────────────

    async def stream(
        self,
        request:      LLMRequest,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream tokens from the LLM provider.
        Yields str tokens as they arrive.
        Stops cleanly if cancel_event is set between tokens.
        Falls back to complete() if provider does not support streaming.
        """
        entry = self._select_provider(request.preferred_provider)

        try:
            async for token in entry.provider.stream(
                request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            ):
                if cancel_event and cancel_event.is_set():
                    return
                self._metrics.on_stream_token(entry.name)
                yield token
        except Exception:
            # Fallback: complete() and yield full response as one token
            response = await self.complete(request, cancel_event=cancel_event)
            yield response.content

    # ── Internal helpers ──────────────────────────────────────────────

    async def _call_provider(self, provider: LLMProvider, request: LLMRequest):
        """Single provider call -- passed to with_retry as the callable."""
        return await asyncio.wait_for(
            provider.generate(
                request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            ),
            timeout=request.timeout_s,
        )

    def _build_response(
        self,
        raw,
        provider_name: str,
        latency_ms:    float,
        retry_count:   int,
    ) -> LLMResponse:
        """Convert raw LLMResponse from app.core.llm into gateway LLMResponse."""
        tokens_used = getattr(raw, "tokens_used", 0)
        return LLMResponse(
            content       = raw.content,
            provider_name = provider_name,
            model         = getattr(raw, "model", ""),
            usage         = TokenUsage(total_tokens=tokens_used),
            latency_ms    = round(latency_ms, 2),
            finish_reason = getattr(raw, "finish_reason", "stop"),
            retry_count   = retry_count,
        )


# ── Gateway exception ─────────────────────────────────────────────────────────

class GatewayError(Exception):
    """Raised when the gateway cannot fulfil a request."""
