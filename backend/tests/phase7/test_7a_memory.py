"""
tests/phase7/test_7a_memory.py
================================
Phase 7A memory tests.

Covers:
  - MemoryHealthMonitor state machine and transitions (7A.1)
  - SentenceTransformerEmbeddingService fallback behaviour (7A.2)
  - QdrantLongTermMemory fallback to InMemoryLongTermMemory (7A.3)
  - MemoryPipelineProvider health-aware routing (7A.4)
  - TestMemoryFailureIsolation -- mandatory ADR-002 gate (7A.5)

All tests are pure -- no live Qdrant, no network, no model downloads.
Qdrant and sentence-transformers are tested via their fallback paths.
"""
import asyncio
import uuid
import pytest

from app.ai.memory.memory_health import MemoryHealthMonitor, MemoryHealthState
from app.ai.memory.sentence_transformer_embeddings import SentenceTransformerEmbeddingService
from app.ai.memory.qdrant_memory import QdrantLongTermMemory, _uuid_to_int, _entry_to_payload, _payload_to_entry
from app.ai.memory.short_term import MemoryEntry, MemoryRole, ShortTermMemory
from app.ai.memory.long_term import InMemoryLongTermMemory, LongTermMemory
from app.ai.memory.embeddings import EmbeddingService
from app.ai.memory import MemoryPipelineProvider
from app.ai.runtime.context import ExecutionContext
from app.ai.runtime.execution import PipelineMemoryProvider


# ── Helpers ───────────────────────────────────────────────────────────────────

def _entry(content: str, importance: float = 0.8) -> MemoryEntry:
    return MemoryEntry(content=content, importance=importance)


def _ctx(user_input: str = "hello", session_id: str = "s1") -> ExecutionContext:
    return ExecutionContext(user_input=user_input, session_id=session_id)


def _make_engine(memory_provider):
    from app.ai.runtime.llm_gateway import LLMGateway
    from app.ai.runtime.execution import ExecutionEngine
    from app.resilience.retry import RetryPolicy, RetryStrategy

    class MockLLMProvider:
        async def generate(self, messages, **kwargs):
            from app.core.llm import LLMResponse as CoreResp
            return CoreResp(content="signal: hold", model="mock", tokens_used=1)
        async def stream(self, messages, **kwargs):
            yield "signal"

    policy = RetryPolicy(max_attempts=1, strategy=RetryStrategy.FIXED, base_delay_s=0.0)
    gw = LLMGateway(retry_policy=policy)
    gw.register("mock", MockLLMProvider())
    return ExecutionEngine(gateway=gw, memory=memory_provider)


# ── TestMemoryHealthMonitor ───────────────────────────────────────────────────

class TestMemoryHealthMonitor:

    def test_initial_state_is_healthy(self):
        m = MemoryHealthMonitor()
        assert m.state == MemoryHealthState.HEALTHY

    def test_is_available_when_healthy(self):
        assert MemoryHealthMonitor().is_available is True

    def test_single_failure_does_not_degrade(self):
        m = MemoryHealthMonitor()
        m.record_failure("t1")
        assert m.state == MemoryHealthState.HEALTHY

    def test_two_failures_degrade(self):
        m = MemoryHealthMonitor()
        m.record_failure("t1")
        m.record_failure("t2")
        assert m.state == MemoryHealthState.DEGRADED

    def test_is_available_when_degraded(self):
        m = MemoryHealthMonitor()
        m.record_failure("t1")
        m.record_failure("t2")
        assert m.is_available is True

    def test_three_failures_from_degraded_goes_offline(self):
        m = MemoryHealthMonitor()
        for _ in range(5):
            m.record_failure("x")
        assert m.state == MemoryHealthState.OFFLINE

    def test_is_not_available_when_offline(self):
        m = MemoryHealthMonitor()
        for _ in range(5):
            m.record_failure("x")
        assert m.is_available is False

    def test_begin_recovery_from_offline(self):
        m = MemoryHealthMonitor()
        for _ in range(5):
            m.record_failure("x")
        m.begin_recovery()
        assert m.state == MemoryHealthState.RECOVERING

    def test_use_cache_only_when_recovering(self):
        m = MemoryHealthMonitor()
        for _ in range(5):
            m.record_failure("x")
        m.begin_recovery()
        assert m.use_cache_only is True

    def test_two_successes_from_recovering_goes_healthy(self):
        m = MemoryHealthMonitor()
        for _ in range(5):
            m.record_failure("x")
        m.begin_recovery()
        m.record_success()
        m.record_success()
        assert m.state == MemoryHealthState.HEALTHY

    def test_success_resets_failure_counter(self):
        m = MemoryHealthMonitor()
        m.record_failure("t1")
        m.record_success()
        m.record_failure("t2")
        assert m.state == MemoryHealthState.HEALTHY

    def test_forbidden_transition_healthy_to_recovering_ignored(self):
        m = MemoryHealthMonitor()
        m._transition(MemoryHealthState.RECOVERING, "illegal")
        assert m.state == MemoryHealthState.HEALTHY

    def test_forbidden_transition_offline_to_healthy_ignored(self):
        m = MemoryHealthMonitor()
        for _ in range(5):
            m.record_failure("x")
        m._transition(MemoryHealthState.HEALTHY, "illegal")
        assert m.state == MemoryHealthState.OFFLINE

    def test_begin_recovery_ignored_when_not_offline(self):
        m = MemoryHealthMonitor()
        m.begin_recovery()
        assert m.state == MemoryHealthState.HEALTHY

    def test_observer_called_on_transition(self):
        events = []
        m = MemoryHealthMonitor()
        m.add_observer(events.append)
        m.record_failure("t1")
        m.record_failure("t2")
        assert len(events) == 1
        assert events[0].to_state == MemoryHealthState.DEGRADED

    def test_observer_exception_does_not_crash_monitor(self):
        def bad_obs(e):
            raise RuntimeError("boom")
        m = MemoryHealthMonitor()
        m.add_observer(bad_obs)
        m.record_failure("t1")
        m.record_failure("t2")
        assert m.state == MemoryHealthState.DEGRADED

    def test_history_records_transitions(self):
        m = MemoryHealthMonitor()
        m.record_failure("t1")
        m.record_failure("t2")
        h = m.history()
        assert len(h) == 1
        assert h[0].from_state == MemoryHealthState.HEALTHY
        assert h[0].to_state   == MemoryHealthState.DEGRADED

    def test_last_event_none_initially(self):
        assert MemoryHealthMonitor().last_event() is None

    def test_full_cycle(self):
        m = MemoryHealthMonitor()
        m.record_failure("t1")
        m.record_failure("t2")
        assert m.state == MemoryHealthState.DEGRADED
        for _ in range(3):
            m.record_failure("x")
        assert m.state == MemoryHealthState.OFFLINE
        m.begin_recovery()
        assert m.state == MemoryHealthState.RECOVERING
        m.record_success()
        m.record_success()
        assert m.state == MemoryHealthState.HEALTHY


# ── TestSentenceTransformerEmbeddingServiceFallback ───────────────────────────

class TestSentenceTransformerEmbeddingServiceFallback:

    def test_encode_returns_list_of_floats(self):
        svc = SentenceTransformerEmbeddingService()
        v   = svc.encode("RELIANCE bullish breakout")
        assert isinstance(v, list)
        assert all(isinstance(x, float) for x in v)

    def test_encode_empty_string_returns_list(self):
        v = SentenceTransformerEmbeddingService().encode("")
        assert isinstance(v, list)

    def test_similarity_in_range(self):
        svc = SentenceTransformerEmbeddingService()
        v1  = svc.encode("bullish breakout")
        v2  = svc.encode("bearish reversal")
        assert -1.0 <= svc.similarity(v1, v2) <= 1.0

    def test_similarity_empty_returns_zero(self):
        assert SentenceTransformerEmbeddingService().similarity([], []) == 0.0

    def test_implements_embedding_service_abc(self):
        assert isinstance(SentenceTransformerEmbeddingService(), EmbeddingService)

    def test_top_k_via_inherited_method(self):
        svc     = SentenceTransformerEmbeddingService()
        entries = [
            MemoryEntry(content="RELIANCE breakout"),
            MemoryEntry(content="NIFTY support"),
            MemoryEntry(content="HDFC earnings"),
        ]
        results = svc.top_k("RELIANCE", entries, k=2)
        assert len(results) <= 2
        assert all(isinstance(score, float) for _, score in results)

    def test_encode_does_not_raise_on_any_input(self):
        svc = SentenceTransformerEmbeddingService()
        for text in ["", "   ", "RELIANCE", "x" * 1000]:
            v = svc.encode(text)
            assert isinstance(v, list)


# ── TestQdrantLongTermMemoryFallback ─────────────────────────────────────────

class TestQdrantLongTermMemoryFallback:

    def _ltm(self) -> QdrantLongTermMemory:
        return QdrantLongTermMemory(url="http://localhost:19999", collection_name="test")

    def test_construction_does_not_raise(self):
        assert self._ltm() is not None

    def test_is_using_fallback(self):
        assert self._ltm().is_using_fallback is True

    def test_implements_long_term_memory_abc(self):
        assert isinstance(self._ltm(), LongTermMemory)

    @pytest.mark.asyncio
    async def test_store_returns_entry_id(self):
        e   = _entry("RELIANCE breakout")
        eid = await self._ltm().store(e)
        assert eid == e.id

    @pytest.mark.asyncio
    async def test_store_below_threshold_skipped(self):
        ltm = self._ltm()
        await ltm.store(_entry("low", importance=0.1))
        assert ltm.size() == 0

    @pytest.mark.asyncio
    async def test_search_returns_list(self):
        ltm = self._ltm()
        await ltm.store(_entry("RELIANCE breakout"))
        assert isinstance(await ltm.search("RELIANCE"), list)

    @pytest.mark.asyncio
    async def test_search_finds_stored_entry(self):
        ltm = self._ltm()
        await ltm.store(_entry("NIFTY support at 22000"))
        results = await ltm.search("NIFTY")
        assert any("NIFTY" in e.content for e in results)

    @pytest.mark.asyncio
    async def test_get_returns_entry(self):
        ltm = self._ltm()
        e   = _entry("retrievable")
        await ltm.store(e)
        found = await ltm.get(e.id)
        assert found is not None
        assert found.content == "retrievable"

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self):
        assert await self._ltm().get(str(uuid.uuid4())) is None

    @pytest.mark.asyncio
    async def test_delete_returns_true(self):
        ltm = self._ltm()
        e   = _entry("to delete")
        await ltm.store(e)
        assert await ltm.delete(e.id) is True

    @pytest.mark.asyncio
    async def test_delete_missing_returns_false(self):
        assert await self._ltm().delete(str(uuid.uuid4())) is False

    @pytest.mark.asyncio
    async def test_all_entries_returns_list(self):
        ltm = self._ltm()
        await ltm.store(_entry("a"))
        await ltm.store(_entry("b"))
        assert len(await ltm.all_entries()) == 2

    def test_size_returns_int(self):
        assert isinstance(self._ltm().size(), int)


# ── TestPayloadHelpers ────────────────────────────────────────────────────────

class TestPayloadHelpers:

    def test_round_trip(self):
        e = _entry("test content")
        r = _payload_to_entry(_entry_to_payload(e))
        assert r.content == e.content
        assert r.id      == e.id

    def test_preserves_role(self):
        e = MemoryEntry(content="x", role=MemoryRole.ASSISTANT)
        r = _payload_to_entry(_entry_to_payload(e))
        assert r.role == MemoryRole.ASSISTANT

    def test_preserves_metadata(self):
        e = _entry("x")
        e.metadata["symbol"] = "RELIANCE"
        r = _payload_to_entry(_entry_to_payload(e))
        assert r.metadata["symbol"] == "RELIANCE"

    def test_uuid_to_int_deterministic(self):
        uid = str(uuid.uuid4())
        assert _uuid_to_int(uid) == _uuid_to_int(uid)

    def test_uuid_to_int_positive(self):
        assert _uuid_to_int(str(uuid.uuid4())) > 0


# ── TestMemoryPipelineProviderHealthRouting ───────────────────────────────────

class TestMemoryPipelineProviderHealthRouting:

    @pytest.mark.asyncio
    async def test_ltm_skipped_when_offline(self):
        ltm = QdrantLongTermMemory(url="http://localhost:19999")
        for _ in range(5):
            ltm.health_monitor.record_failure("forced")
        assert not ltm.health_monitor.is_available
        provider = MemoryPipelineProvider(long_term=ltm)
        ctx      = _ctx("RELIANCE breakout")
        await provider.load(ctx)
        assert isinstance(ctx.memory_context, list)

    @pytest.mark.asyncio
    async def test_ltm_used_when_healthy(self):
        ltm = InMemoryLongTermMemory()
        await ltm.store(_entry("NIFTY at support"))
        provider = MemoryPipelineProvider(long_term=ltm)
        ctx      = _ctx("NIFTY support")
        await provider.load(ctx)
        assert any("NIFTY" in e.content for e in ctx.memory_context)

    @pytest.mark.asyncio
    async def test_stm_always_works_regardless_of_ltm_health(self):
        ltm = QdrantLongTermMemory(url="http://localhost:19999")
        for _ in range(5):
            ltm.health_monitor.record_failure("forced")
        provider = MemoryPipelineProvider(long_term=ltm)
        ctx      = _ctx("test input")
        await provider.load(ctx)
        assert provider.short_term.size >= 1


# ── TestMemoryFailureIsolation (ADR-002 mandatory gate) ───────────────────────

class TestMemoryFailureIsolation:
    """
    ADR-002 mandatory test class. All 5 scenarios must pass before
    Phase 7A merges to master.

    Proves: if every memory component fails, the trading pipeline
    still produces a valid result. The trading engine never knows
    memory exists.
    """

    @pytest.mark.asyncio
    async def test_scenario_1_qdrant_unavailable(self):
        """Qdrant unavailable → fallback active → trading continues."""
        ltm      = QdrantLongTermMemory(url="http://localhost:19999")
        provider = MemoryPipelineProvider(long_term=ltm)
        engine   = _make_engine(provider)
        result   = await engine.run("analyse RELIANCE", session_id="s1")
        assert result is not None
        assert result.response is not None

    @pytest.mark.asyncio
    async def test_scenario_2_embedding_service_failure(self):
        """Embedding service raises → pipeline continues with empty LTM hits."""
        class BrokenEmbeddings(EmbeddingService):
            def encode(self, text):
                raise RuntimeError("embedding exploded")
            def similarity(self, a, b):
                raise RuntimeError("embedding exploded")

        provider = MemoryPipelineProvider(
            long_term=InMemoryLongTermMemory(),
            embeddings=BrokenEmbeddings(),
        )
        engine = _make_engine(provider)
        result = await engine.run("analyse NIFTY", session_id="s1")
        assert result is not None
        assert result.response is not None

    @pytest.mark.asyncio
    async def test_scenario_3_memory_load_raises(self):
        """Memory.load() raises → pipeline continues (existing behaviour)."""
        class ExplodingMemory(PipelineMemoryProvider):
            async def load(self, ctx):
                raise RuntimeError("memory exploded")

        engine = _make_engine(ExplodingMemory())
        result = await engine.run("analyse HDFC", session_id="s1")
        # ExecutionEngine already handles memory failure gracefully (Phase 6)
        assert result is not None

    @pytest.mark.asyncio
    async def test_scenario_4_memory_returns_empty(self):
        """Memory returns [] → pipeline continues normally."""
        class EmptyMemory(PipelineMemoryProvider):
            async def load(self, ctx):
                ctx.memory_context = []

        engine = _make_engine(EmptyMemory())
        result = await engine.run("analyse INFY", session_id="s1")
        assert result is not None
        assert result.response is not None

    @pytest.mark.asyncio
    async def test_scenario_5_memory_returns_malformed_data(self):
        """Memory returns corrupt data → pipeline continues."""
        class MalformedMemory(PipelineMemoryProvider):
            async def load(self, ctx):
                ctx.memory_context = [None, "not an entry", 42, {"bad": "data"}]

        engine = _make_engine(MalformedMemory())
        result = await engine.run("analyse TCS", session_id="s1")
        assert result is not None
        assert result.response is not None
