"""
tests/phase6/test_6a_llm_gateway.py
=====================================
Unit tests for LLMGateway (Task 6A.2).

All LLM provider calls are mocked -- no network, no API keys required.
"""
import asyncio
import pytest

from app.core.llm import LLMProvider, LLMMessage
from app.core.llm import LLMResponse as CoreLLMResponse
from app.ai.runtime.llm_gateway import (
    LLMGateway,
    LLMRequest,
    LLMResponse,
    TokenUsage,
    GatewayError,
    GatewayMetricsCollector,
    _NoOpMetrics,
)
from app.resilience.retry import RetryPolicy, RetryStrategy


# ── Mock providers ────────────────────────────────────────────────────────────

class MockProvider(LLMProvider):
    """Succeeds immediately with a fixed response."""

    def __init__(self, name: str = "mock", model: str = "mock-model", tokens: int = 42):
        self.name   = name
        self.model  = model
        self.tokens = tokens
        self.call_count = 0

    async def generate(self, messages, **kwargs) -> CoreLLMResponse:
        self.call_count += 1
        return CoreLLMResponse(
            content=f"response from {self.name}",
            model=self.model,
            tokens_used=self.tokens,
            finish_reason="stop",
        )

    async def stream(self, messages, **kwargs):
        for token in ["hello", " ", "world"]:
            yield token


class FailingProvider(LLMProvider):
    """Always raises an exception."""

    def __init__(self, error: Exception = None):
        self.error = error or RuntimeError("provider failed")
        self.call_count = 0

    async def generate(self, messages, **kwargs):
        self.call_count += 1
        raise self.error

    async def stream(self, messages, **kwargs):
        raise self.error
        yield  # make it a generator


class FailThenSucceedProvider(LLMProvider):
    """Fails the first N calls, then succeeds."""

    def __init__(self, fail_times: int = 1):
        self.fail_times  = fail_times
        self.call_count  = 0

    async def generate(self, messages, **kwargs) -> CoreLLMResponse:
        self.call_count += 1
        if self.call_count <= self.fail_times:
            raise RuntimeError(f"fail #{self.call_count}")
        return CoreLLMResponse(content="recovered", model="m", tokens_used=10)

    async def stream(self, messages, **kwargs):
        yield "token"


class CapturingMetrics(GatewayMetricsCollector):
    """Records all metric calls for assertion."""

    def __init__(self):
        self.completed:  list = []
        self.failed:     list = []
        self.stream_tokens: int = 0

    def on_call_complete(self, response: LLMResponse) -> None:
        self.completed.append(response)

    def on_call_failed(self, provider_name, error, latency_ms) -> None:
        self.failed.append((provider_name, error, latency_ms))

    def on_stream_token(self, provider_name: str) -> None:
        self.stream_tokens += 1


# ── Helpers ───────────────────────────────────────────────────────────────────

def _no_retry_policy() -> RetryPolicy:
    """Policy that never retries -- makes tests fast."""
    return RetryPolicy(max_attempts=1, strategy=RetryStrategy.FIXED, base_delay_s=0.0)


def _make_request(**kwargs) -> LLMRequest:
    msgs = kwargs.pop("messages", [LLMMessage(role="user", content="hello")])
    return LLMRequest(messages=msgs, **kwargs)


# ── Registration ──────────────────────────────────────────────────────────────

class TestRegistration:

    def test_register_single_provider(self):
        gw = LLMGateway()
        gw.register("p1", MockProvider())
        assert gw.has_provider("p1")

    def test_first_registered_becomes_default(self):
        gw = LLMGateway()
        gw.register("p1", MockProvider())
        assert gw._default_name == "p1"

    def test_explicit_default_overrides_first(self):
        gw = LLMGateway()
        gw.register("p1", MockProvider())
        gw.register("p2", MockProvider(), default=True)
        assert gw._default_name == "p2"

    def test_set_default_changes_default(self):
        gw = LLMGateway()
        gw.register("p1", MockProvider())
        gw.register("p2", MockProvider())
        gw.set_default("p2")
        assert gw._default_name == "p2"

    def test_set_default_unknown_raises(self):
        gw = LLMGateway()
        with pytest.raises(ValueError):
            gw.set_default("nonexistent")

    def test_registered_providers_returns_names(self):
        gw = LLMGateway()
        gw.register("a", MockProvider())
        gw.register("b", MockProvider())
        assert set(gw.registered_providers()) == {"a", "b"}

    def test_no_providers_raises_on_complete(self):
        gw = LLMGateway(retry_policy=_no_retry_policy())
        with pytest.raises(GatewayError, match="No LLM providers"):
            asyncio.get_event_loop().run_until_complete(
                gw.complete(_make_request())
            )


# ── Provider selection ────────────────────────────────────────────────────────

class TestProviderSelection:

    @pytest.mark.asyncio
    async def test_uses_default_provider(self):
        p = MockProvider("default")
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("default", p)
        await gw.complete(_make_request())
        assert p.call_count == 1

    @pytest.mark.asyncio
    async def test_preferred_provider_overrides_default(self):
        p1 = MockProvider("p1")
        p2 = MockProvider("p2")
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("p1", p1, default=True)
        gw.register("p2", p2)
        await gw.complete(_make_request(preferred_provider="p2"))
        assert p1.call_count == 0
        assert p2.call_count == 1

    @pytest.mark.asyncio
    async def test_unknown_preferred_falls_back_to_default(self):
        p = MockProvider("default")
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("default", p)
        await gw.complete(_make_request(preferred_provider="nonexistent"))
        assert p.call_count == 1

    @pytest.mark.asyncio
    async def test_priority_fallback_selects_lowest_priority_number(self):
        low  = MockProvider("low")
        high = MockProvider("high")
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("low",  low,  priority=10)
        gw.register("high", high, priority=5)
        # No explicit default -- should pick priority=5
        gw._default_name = None
        await gw.complete(_make_request())
        assert high.call_count == 1
        assert low.call_count == 0


# ── Complete response ─────────────────────────────────────────────────────────

class TestCompleteResponse:

    @pytest.mark.asyncio
    async def test_returns_llm_response_type(self):
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("p", MockProvider())
        result = await gw.complete(_make_request())
        assert isinstance(result, LLMResponse)

    @pytest.mark.asyncio
    async def test_response_content_matches_provider(self):
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("p", MockProvider("p"))
        result = await gw.complete(_make_request())
        assert result.content == "response from p"

    @pytest.mark.asyncio
    async def test_response_provider_name_set(self):
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("gemini", MockProvider("gemini"))
        result = await gw.complete(_make_request())
        assert result.provider_name == "gemini"

    @pytest.mark.asyncio
    async def test_response_model_set(self):
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("p", MockProvider(model="gemini-2.0-flash"))
        result = await gw.complete(_make_request())
        assert result.model == "gemini-2.0-flash"

    @pytest.mark.asyncio
    async def test_response_token_usage_set(self):
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("p", MockProvider(tokens=99))
        result = await gw.complete(_make_request())
        assert result.usage.total_tokens == 99

    @pytest.mark.asyncio
    async def test_response_latency_non_negative(self):
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("p", MockProvider())
        result = await gw.complete(_make_request())
        assert result.latency_ms >= 0.0

    @pytest.mark.asyncio
    async def test_response_finish_reason_set(self):
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("p", MockProvider())
        result = await gw.complete(_make_request())
        assert result.finish_reason == "stop"


# ── Fallback ──────────────────────────────────────────────────────────────────

class TestFallback:

    @pytest.mark.asyncio
    async def test_falls_back_to_second_provider_on_failure(self):
        bad  = FailingProvider()
        good = MockProvider("good")
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("bad",  bad,  default=True)
        gw.register("good", good, priority=20)
        result = await gw.complete(_make_request())
        assert result.content == "response from good"

    @pytest.mark.asyncio
    async def test_raises_gateway_error_when_all_fail(self):
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("p1", FailingProvider())
        gw.register("p2", FailingProvider())
        with pytest.raises(GatewayError):
            await gw.complete(_make_request())

    @pytest.mark.asyncio
    async def test_fallback_provider_name_in_response(self):
        bad  = FailingProvider()
        good = MockProvider("fallback_provider")
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("bad",      bad,  default=True)
        gw.register("fallback", good, priority=20)
        result = await gw.complete(_make_request())
        assert result.provider_name == "fallback"


# ── Cancellation ──────────────────────────────────────────────────────────────

class TestCancellation:

    @pytest.mark.asyncio
    async def test_cancelled_event_raises_gateway_error(self):
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("p1", FailingProvider())  # primary fails
        gw.register("p2", MockProvider())     # fallback would succeed

        cancel = asyncio.Event()
        cancel.set()  # already cancelled

        with pytest.raises(GatewayError, match="cancelled"):
            await gw.complete(_make_request(), cancel_event=cancel)

    @pytest.mark.asyncio
    async def test_not_cancelled_completes_normally(self):
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("p", MockProvider())
        cancel = asyncio.Event()  # not set
        result = await gw.complete(_make_request(), cancel_event=cancel)
        assert result.content is not None


# ── Streaming ─────────────────────────────────────────────────────────────────

class TestStreaming:

    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self):
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("p", MockProvider())
        tokens = []
        async for token in gw.stream(_make_request()):
            tokens.append(token)
        assert tokens == ["hello", " ", "world"]

    @pytest.mark.asyncio
    async def test_stream_stops_on_cancel(self):
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("p", MockProvider())
        cancel = asyncio.Event()
        tokens = []
        async for token in gw.stream(_make_request(), cancel_event=cancel):
            tokens.append(token)
            cancel.set()  # cancel after first token
        assert len(tokens) == 1

    @pytest.mark.asyncio
    async def test_stream_falls_back_to_complete_on_provider_error(self):
        gw = LLMGateway(retry_policy=_no_retry_policy())
        gw.register("p", FailingProvider())
        gw.register("fallback", MockProvider("fallback"))
        tokens = []
        async for token in gw.stream(_make_request()):
            tokens.append(token)
        assert len(tokens) == 1
        assert "fallback" in tokens[0]


# ── Metrics ───────────────────────────────────────────────────────────────────

class TestMetrics:

    @pytest.mark.asyncio
    async def test_on_call_complete_fired_on_success(self):
        metrics = CapturingMetrics()
        gw = LLMGateway(retry_policy=_no_retry_policy(), metrics=metrics)
        gw.register("p", MockProvider())
        await gw.complete(_make_request())
        assert len(metrics.completed) == 1

    @pytest.mark.asyncio
    async def test_on_call_failed_fired_when_all_fail(self):
        metrics = CapturingMetrics()
        gw = LLMGateway(retry_policy=_no_retry_policy(), metrics=metrics)
        gw.register("p", FailingProvider())
        with pytest.raises(GatewayError):
            await gw.complete(_make_request())
        assert len(metrics.failed) == 1

    @pytest.mark.asyncio
    async def test_on_stream_token_fired_per_token(self):
        metrics = CapturingMetrics()
        gw = LLMGateway(retry_policy=_no_retry_policy(), metrics=metrics)
        gw.register("p", MockProvider())
        async for _ in gw.stream(_make_request()):
            pass
        assert metrics.stream_tokens == 3  # "hello", " ", "world"

    @pytest.mark.asyncio
    async def test_completed_response_has_correct_latency(self):
        metrics = CapturingMetrics()
        gw = LLMGateway(retry_policy=_no_retry_policy(), metrics=metrics)
        gw.register("p", MockProvider())
        await gw.complete(_make_request())
        assert metrics.completed[0].latency_ms >= 0.0


# ── LLMRequest / LLMResponse models ──────────────────────────────────────────

class TestModels:

    def test_llm_request_defaults(self):
        req = LLMRequest(messages=[])
        assert req.temperature == 0.7
        assert req.max_tokens == 1024
        assert req.stream is False
        assert req.preferred_provider is None
        assert req.timeout_s == 60.0
        assert req.metadata == {}

    def test_llm_response_fields(self):
        resp = LLMResponse(
            content="hi",
            provider_name="gemini",
            model="gemini-2.0-flash",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            latency_ms=123.4,
        )
        assert resp.content == "hi"
        assert resp.usage.total_tokens == 30
        assert resp.latency_ms == 123.4
        assert resp.retry_count == 0
        assert resp.metadata == {}

    def test_token_usage_defaults(self):
        u = TokenUsage()
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.total_tokens == 0


# ── Domain agnosticism ────────────────────────────────────────────────────────

class TestDomainAgnosticism:

    def test_gateway_has_no_trading_fields(self):
        gw = LLMGateway()
        trading_attrs = ["symbol", "stock", "candle", "broker", "portfolio",
                         "market", "nifty", "rsi", "macd"]
        for attr in trading_attrs:
            assert not hasattr(gw, attr), (
                f"Domain attribute '{attr}' found on LLMGateway"
            )

    def test_llm_request_has_no_trading_fields(self):
        req = LLMRequest(messages=[])
        trading_attrs = ["symbol", "stock", "candle", "broker", "portfolio"]
        for attr in trading_attrs:
            assert not hasattr(req, attr), (
                f"Domain attribute '{attr}' found on LLMRequest"
            )

    def test_metadata_carries_domain_context(self):
        """Domain data belongs in metadata, not as first-class fields."""
        req = LLMRequest(
            messages=[],
            metadata={"domain": "trading", "symbol": "RELIANCE"},
        )
        assert req.metadata["domain"] == "trading"
