"""
tests/phase6/test_6b_memory.py
================================
Unit tests for Phase 6B -- Memory System.

Covers:
  - MemoryEntry (6B.1)
  - ShortTermMemory ring buffer (6B.1)
  - ShortTermMemoryAdapter (6B.1)
  - InMemoryLongTermMemory (6B.2)
  - EmbeddingService / SimpleEmbeddingService (6B.3)
  - MemoryPipelineProvider integration (6B.__init__)
  - TestDomainAgnosticism (mandatory)

All tests are pure -- no network, no I/O, no LLM calls.
"""
import pytest

from app.ai.memory.short_term import MemoryEntry, MemoryRole, ShortTermMemory, ShortTermMemoryAdapter
from app.ai.memory.long_term import InMemoryLongTermMemory, LongTermMemory, SearchResult
from app.ai.memory.embeddings import SimpleEmbeddingService, _l2_normalise, _dot
from app.ai.memory import MemoryPipelineProvider
from app.ai.runtime.context import ExecutionContext


# ── Helpers ───────────────────────────────────────────────────────────────────

def _entry(content: str, importance: float = 0.5, session_id: str = "") -> MemoryEntry:
    return MemoryEntry(content=content, importance=importance, session_id=session_id)


def _ctx(user_input: str = "hello", session_id: str = "s1") -> ExecutionContext:
    return ExecutionContext(user_input=user_input, session_id=session_id)


# ── TestMemoryEntry ───────────────────────────────────────────────────────────

class TestMemoryEntry:

    def test_id_auto_generated(self):
        e = MemoryEntry()
        assert len(e.id) == 36

    def test_two_entries_have_different_ids(self):
        assert MemoryEntry().id != MemoryEntry().id

    def test_default_role_is_user(self):
        e = MemoryEntry()
        assert e.role == MemoryRole.USER

    def test_default_importance_is_half(self):
        e = MemoryEntry()
        assert e.importance == 0.5

    def test_timestamp_auto_set(self):
        e = MemoryEntry()
        assert e.timestamp > 0

    def test_age_seconds_non_negative(self):
        e = MemoryEntry()
        assert e.age_seconds() >= 0.0

    def test_embedding_defaults_none(self):
        e = MemoryEntry()
        assert e.embedding is None

    def test_metadata_is_domain_escape_hatch(self):
        e = MemoryEntry()
        e.metadata["symbol"] = "RELIANCE"
        assert e.metadata["symbol"] == "RELIANCE"

    def test_all_roles_valid(self):
        for role in MemoryRole:
            e = MemoryEntry(role=role)
            assert e.role == role


# ── TestShortTermMemory ───────────────────────────────────────────────────────

class TestShortTermMemory:

    def test_starts_empty(self):
        stm = ShortTermMemory()
        assert stm.size == 0

    def test_add_returns_entry(self):
        stm = ShortTermMemory()
        e = stm.add("hello")
        assert isinstance(e, MemoryEntry)
        assert e.content == "hello"

    def test_size_increments(self):
        stm = ShortTermMemory()
        stm.add("a")
        stm.add("b")
        assert stm.size == 2

    def test_ring_buffer_evicts_oldest(self):
        stm = ShortTermMemory(capacity=3)
        stm.add("first")
        stm.add("second")
        stm.add("third")
        stm.add("fourth")   # evicts "first"
        assert stm.size == 3
        contents = [e.content for e in stm.all_entries()]
        assert "first" not in contents
        assert "fourth" in contents

    def test_capacity_enforced(self):
        stm = ShortTermMemory(capacity=5)
        for i in range(10):
            stm.add(f"entry {i}")
        assert stm.size == 5

    def test_is_full_flag(self):
        stm = ShortTermMemory(capacity=2)
        assert not stm.is_full
        stm.add("a")
        stm.add("b")
        assert stm.is_full

    def test_recent_returns_last_n(self):
        stm = ShortTermMemory()
        for i in range(10):
            stm.add(f"msg {i}")
        recent = stm.recent(n=3)
        assert len(recent) == 3
        assert recent[-1].content == "msg 9"

    def test_recent_filtered_by_session(self):
        stm = ShortTermMemory()
        stm.add("s1 msg", session_id="s1")
        stm.add("s2 msg", session_id="s2")
        stm.add("s1 msg2", session_id="s1")
        result = stm.recent(n=10, session_id="s1")
        assert all(e.session_id == "s1" for e in result)
        assert len(result) == 2

    def test_search_keyword_match(self):
        stm = ShortTermMemory()
        stm.add("the weather is sunny")
        stm.add("I like coffee")
        stm.add("weather forecast tomorrow")
        hits = stm.search("weather")
        assert len(hits) == 2

    def test_search_case_insensitive(self):
        stm = ShortTermMemory()
        stm.add("The WEATHER is nice")
        hits = stm.search("weather")
        assert len(hits) == 1

    def test_search_top_k_respected(self):
        stm = ShortTermMemory()
        for i in range(10):
            stm.add(f"weather report {i}")
        hits = stm.search("weather", top_k=3)
        assert len(hits) == 3

    def test_search_no_match_returns_empty(self):
        stm = ShortTermMemory()
        stm.add("hello world")
        assert stm.search("xyz") == []

    def test_clear_all(self):
        stm = ShortTermMemory()
        stm.add("a")
        stm.add("b")
        removed = stm.clear()
        assert removed == 2
        assert stm.size == 0

    def test_clear_by_session(self):
        stm = ShortTermMemory()
        stm.add("s1", session_id="s1")
        stm.add("s2", session_id="s2")
        stm.add("s1b", session_id="s1")
        removed = stm.clear(session_id="s1")
        assert removed == 2
        assert stm.size == 1
        assert stm.all_entries()[0].session_id == "s2"

    def test_add_entry_directly(self):
        stm = ShortTermMemory()
        e = MemoryEntry(content="direct", role=MemoryRole.ASSISTANT)
        stm.add_entry(e)
        assert stm.size == 1
        assert stm.all_entries()[0].content == "direct"

    def test_stats_structure(self):
        stm = ShortTermMemory()
        stm.add("hello", role=MemoryRole.USER)
        stm.add("hi",    role=MemoryRole.ASSISTANT)
        s = stm.stats()
        assert s["size"]     == 2
        assert s["capacity"] == ShortTermMemory.MAX_CAPACITY
        assert "by_role" in s

    def test_invalid_capacity_raises(self):
        with pytest.raises(ValueError):
            ShortTermMemory(capacity=0)

    def test_max_capacity_constant(self):
        assert ShortTermMemory.MAX_CAPACITY == 50


# ── TestShortTermMemoryAdapter ────────────────────────────────────────────────

class TestShortTermMemoryAdapter:

    @pytest.mark.asyncio
    async def test_load_populates_memory_context(self):
        stm     = ShortTermMemory()
        adapter = ShortTermMemoryAdapter(stm, max_turns=10)
        ctx     = _ctx("what is the weather?", "s1")
        await adapter.load(ctx)
        assert len(ctx.memory_context) >= 1

    @pytest.mark.asyncio
    async def test_load_records_user_turn(self):
        stm     = ShortTermMemory()
        adapter = ShortTermMemoryAdapter(stm)
        ctx     = _ctx("hello", "s1")
        await adapter.load(ctx)
        assert stm.size == 1
        assert stm.all_entries()[0].content == "hello"

    @pytest.mark.asyncio
    async def test_load_respects_max_turns(self):
        stm = ShortTermMemory()
        for i in range(20):
            stm.add(f"old msg {i}", session_id="s1")
        adapter = ShortTermMemoryAdapter(stm, max_turns=5)
        ctx     = _ctx("new msg", "s1")
        await adapter.load(ctx)
        # memory_context should have at most max_turns entries
        assert len(ctx.memory_context) <= 5

    @pytest.mark.asyncio
    async def test_multiple_loads_accumulate(self):
        stm     = ShortTermMemory()
        adapter = ShortTermMemoryAdapter(stm)
        await adapter.load(_ctx("msg1", "s1"))
        await adapter.load(_ctx("msg2", "s1"))
        assert stm.size == 2


# ── TestInMemoryLongTermMemory ────────────────────────────────────────────────

class TestInMemoryLongTermMemory:

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self):
        ltm   = InMemoryLongTermMemory()
        entry = _entry("user prefers concise answers", importance=0.8)
        eid   = await ltm.store(entry)
        assert eid == entry.id
        assert ltm.size() == 1

    @pytest.mark.asyncio
    async def test_below_threshold_not_stored(self):
        ltm   = InMemoryLongTermMemory(importance_threshold=0.6)
        entry = _entry("low importance fact", importance=0.3)
        eid   = await ltm.store(entry)
        assert eid == entry.id   # id still returned
        assert ltm.size() == 0   # but not stored

    @pytest.mark.asyncio
    async def test_at_threshold_is_stored(self):
        ltm   = InMemoryLongTermMemory(importance_threshold=0.6)
        entry = _entry("exactly at threshold", importance=0.6)
        await ltm.store(entry)
        assert ltm.size() == 1

    @pytest.mark.asyncio
    async def test_get_by_id(self):
        ltm   = InMemoryLongTermMemory()
        entry = _entry("retrievable", importance=0.9)
        await ltm.store(entry)
        found = await ltm.get(entry.id)
        assert found is not None
        assert found.content == "retrievable"

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self):
        ltm = InMemoryLongTermMemory()
        assert await ltm.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_delete_existing(self):
        ltm   = InMemoryLongTermMemory()
        entry = _entry("to delete", importance=0.9)
        await ltm.store(entry)
        deleted = await ltm.delete(entry.id)
        assert deleted is True
        assert ltm.size() == 0

    @pytest.mark.asyncio
    async def test_delete_missing_returns_false(self):
        ltm = InMemoryLongTermMemory()
        assert await ltm.delete("ghost") is False

    @pytest.mark.asyncio
    async def test_search_keyword(self):
        ltm = InMemoryLongTermMemory()
        await ltm.store(_entry("user likes dark mode", importance=0.8))
        await ltm.store(_entry("user prefers short answers", importance=0.8))
        await ltm.store(_entry("system timezone is UTC", importance=0.8))
        hits = await ltm.search("user")
        assert len(hits) == 2

    @pytest.mark.asyncio
    async def test_search_top_k(self):
        ltm = InMemoryLongTermMemory()
        for i in range(10):
            await ltm.store(_entry(f"fact about weather {i}", importance=0.9))
        hits = await ltm.search("weather", top_k=3)
        assert len(hits) == 3

    @pytest.mark.asyncio
    async def test_search_sorted_by_importance(self):
        ltm = InMemoryLongTermMemory()
        await ltm.store(_entry("low importance weather", importance=0.7))
        await ltm.store(_entry("high importance weather", importance=0.95))
        hits = await ltm.search("weather")
        assert hits[0].importance >= hits[-1].importance

    @pytest.mark.asyncio
    async def test_all_entries(self):
        ltm = InMemoryLongTermMemory()
        await ltm.store(_entry("a", importance=0.9))
        await ltm.store(_entry("b", importance=0.9))
        all_e = await ltm.all_entries()
        assert len(all_e) == 2

    @pytest.mark.asyncio
    async def test_stats(self):
        ltm = InMemoryLongTermMemory()
        await ltm.store(_entry("x", importance=0.8))
        s = ltm.stats()
        assert s["size"] == 1
        assert "avg_importance" in s
        assert s["threshold"] == 0.6

    def test_invalid_threshold_raises(self):
        with pytest.raises(ValueError):
            InMemoryLongTermMemory(importance_threshold=1.5)

    def test_ltm_is_abc_subclass(self):
        ltm = InMemoryLongTermMemory()
        assert isinstance(ltm, LongTermMemory)


# ── TestSimpleEmbeddingService ────────────────────────────────────────────────

class TestSimpleEmbeddingService:

    def test_encode_returns_list_of_floats(self):
        svc = SimpleEmbeddingService()
        v   = svc.encode("hello world")
        assert isinstance(v, list)
        assert all(isinstance(x, float) for x in v)

    def test_encode_empty_string_returns_empty(self):
        svc = SimpleEmbeddingService()
        v   = svc.encode("")
        assert v == []

    def test_encode_same_text_same_vector(self):
        svc = SimpleEmbeddingService()
        v1  = svc.encode("the quick brown fox")
        v2  = svc.encode("the quick brown fox")
        assert v1 == v2

    def test_encode_different_text_different_vector(self):
        svc = SimpleEmbeddingService()
        v1  = svc.encode("hello world")
        v2  = svc.encode("goodbye moon")
        assert v1 != v2

    def test_vector_is_l2_normalised(self):
        import math
        svc  = SimpleEmbeddingService()
        v    = svc.encode("normalised vector test")
        norm = math.sqrt(sum(x * x for x in v))
        assert abs(norm - 1.0) < 1e-6

    def test_similarity_identical_texts(self):
        svc = SimpleEmbeddingService()
        v   = svc.encode("identical text")
        sim = svc.similarity(v, v)
        assert abs(sim - 1.0) < 1e-5

    def test_similarity_empty_vectors_returns_zero(self):
        svc = SimpleEmbeddingService()
        assert svc.similarity([], []) == 0.0

    def test_similarity_orthogonal_is_zero(self):
        svc = SimpleEmbeddingService()
        # Encode two completely disjoint vocabularies
        v1  = svc.encode("alpha beta gamma")
        v2  = svc.encode("delta epsilon zeta")
        sim = svc.similarity(v1, v2)
        assert sim == 0.0

    def test_similarity_partial_overlap(self):
        svc = SimpleEmbeddingService()
        v1  = svc.encode("the quick brown fox")
        v2  = svc.encode("the slow brown dog")
        sim = svc.similarity(v1, v2)
        assert 0.0 < sim < 1.0

    def test_similarity_handles_different_length_vectors(self):
        svc = SimpleEmbeddingService()
        v1  = svc.encode("hello")
        v2  = svc.encode("hello world extra words here")
        # Should not raise
        sim = svc.similarity(v1, v2)
        assert 0.0 <= sim <= 1.0

    def test_vocab_grows_with_new_words(self):
        svc = SimpleEmbeddingService()
        svc.encode("alpha beta")
        size1 = svc.vocab_size()
        svc.encode("gamma delta")
        size2 = svc.vocab_size()
        assert size2 > size1

    def test_top_k_returns_sorted_by_score(self):
        svc     = SimpleEmbeddingService()
        entries = [
            _entry("the weather is sunny today"),
            _entry("I enjoy coffee in the morning"),
            _entry("weather forecast shows rain"),
            _entry("stock market is volatile"),
        ]
        results = svc.top_k("weather forecast", entries, k=2)
        assert len(results) == 2
        assert results[0][1] >= results[1][1]   # sorted descending

    def test_top_k_min_score_filters(self):
        svc     = SimpleEmbeddingService()
        entries = [_entry("completely unrelated xyz abc")]
        results = svc.top_k("weather", entries, k=5, min_score=0.9)
        assert results == []

    def test_top_k_uses_existing_embedding(self):
        svc   = SimpleEmbeddingService()
        entry = _entry("pre-encoded content")
        entry.embedding = svc.encode("pre-encoded content")
        results = svc.top_k("pre-encoded", [entry], k=1)
        assert len(results) == 1

    def test_encode_entries_populates_embeddings(self):
        svc     = SimpleEmbeddingService()
        entries = [_entry("first"), _entry("second"), _entry("third")]
        svc.encode_entries(entries)
        assert all(e.embedding is not None for e in entries)
        assert all(len(e.embedding) > 0 for e in entries)


# ── TestMemoryPipelineProvider ────────────────────────────────────────────────

class TestMemoryPipelineProvider:

    @pytest.mark.asyncio
    async def test_load_with_stm_only(self):
        provider = MemoryPipelineProvider()
        ctx      = _ctx("hello", "s1")
        await provider.load(ctx)
        assert isinstance(ctx.memory_context, list)
        assert len(ctx.memory_context) >= 1

    @pytest.mark.asyncio
    async def test_load_records_user_turn_in_stm(self):
        provider = MemoryPipelineProvider()
        ctx      = _ctx("test input", "s1")
        await provider.load(ctx)
        assert provider.short_term.size == 1

    @pytest.mark.asyncio
    async def test_load_with_ltm_keyword_fallback(self):
        ltm      = InMemoryLongTermMemory()
        await ltm.store(_entry("user prefers dark mode", importance=0.9))
        provider = MemoryPipelineProvider(long_term=ltm)
        ctx      = _ctx("dark mode preference", "s1")
        await provider.load(ctx)
        contents = [e.content for e in ctx.memory_context]
        assert any("dark mode" in c for c in contents)

    @pytest.mark.asyncio
    async def test_load_with_full_stack(self):
        stm = ShortTermMemory()
        ltm = InMemoryLongTermMemory()
        emb = SimpleEmbeddingService()
        await ltm.store(_entry("user likes concise answers", importance=0.9))
        provider = MemoryPipelineProvider(stm, ltm, emb)
        ctx      = _ctx("concise response please", "s1")
        await provider.load(ctx)
        assert isinstance(ctx.memory_context, list)

    @pytest.mark.asyncio
    async def test_no_duplicates_in_memory_context(self):
        stm = ShortTermMemory()
        ltm = InMemoryLongTermMemory()
        # Add same entry to both STM and LTM
        entry = _entry("shared fact", importance=0.9)
        stm.add_entry(entry)
        await ltm.store(entry)
        provider = MemoryPipelineProvider(stm, ltm)
        ctx      = _ctx("shared fact", "s1")
        await provider.load(ctx)
        ids = [e.id for e in ctx.memory_context]
        assert len(ids) == len(set(ids))

    @pytest.mark.asyncio
    async def test_multiple_sessions_isolated(self):
        provider = MemoryPipelineProvider()
        await provider.load(_ctx("s1 message", "s1"))
        await provider.load(_ctx("s2 message", "s2"))
        ctx = _ctx("s1 query", "s1")
        await provider.load(ctx)
        # s1 context should not contain s2 messages
        contents = [e.content for e in ctx.memory_context]
        assert not any("s2 message" in c for c in contents)

    def test_accessors(self):
        stm      = ShortTermMemory()
        ltm      = InMemoryLongTermMemory()
        emb      = SimpleEmbeddingService()
        provider = MemoryPipelineProvider(stm, ltm, emb)
        assert provider.short_term is stm
        assert provider.long_term  is ltm
        assert provider.embeddings is emb

    def test_default_construction(self):
        provider = MemoryPipelineProvider()
        assert provider.short_term is not None
        assert provider.long_term  is None
        assert provider.embeddings is None


# ── TestMemoryBrainIntegration ────────────────────────────────────────────────

class TestMemoryBrainIntegration:
    """
    Verify that MemoryPipelineProvider integrates correctly with
    ExecutionEngine as a PipelineMemoryProvider.
    """

    def _make_engine_with_memory(self):
        from app.ai.runtime.llm_gateway import LLMGateway
        from app.ai.runtime.execution import ExecutionEngine
        from app.resilience.retry import RetryPolicy, RetryStrategy

        class MockProvider:
            async def generate(self, messages, **kwargs):
                from app.core.llm import LLMResponse as CoreResp
                return CoreResp(content="mock", model="mock", tokens_used=5)
            async def stream(self, messages, **kwargs):
                yield "token"

        policy = RetryPolicy(max_attempts=1, strategy=RetryStrategy.FIXED, base_delay_s=0.0)
        gw     = LLMGateway(retry_policy=policy)
        gw.register("mock", MockProvider())
        memory = MemoryPipelineProvider()
        return ExecutionEngine(gateway=gw, memory=memory), memory

    @pytest.mark.asyncio
    async def test_engine_populates_memory_context(self):
        engine, memory = self._make_engine_with_memory()
        result = await engine.run("hello", session_id="s1")
        assert result.context.memory_context is not None

    @pytest.mark.asyncio
    async def test_memory_accumulates_across_requests(self):
        engine, memory = self._make_engine_with_memory()
        await engine.run("first message", session_id="s1")
        await engine.run("second message", session_id="s1")
        assert memory.short_term.size == 2

    @pytest.mark.asyncio
    async def test_memory_failure_is_non_fatal(self):
        """Memory load failure must not abort the pipeline (architecture §18)."""
        from app.ai.runtime.execution import PipelineMemoryProvider, ExecutionEngine
        from app.ai.runtime.llm_gateway import LLMGateway
        from app.resilience.retry import RetryPolicy, RetryStrategy

        class BrokenMemory(PipelineMemoryProvider):
            async def load(self, ctx):
                raise RuntimeError("memory exploded")

        class MockProvider:
            async def generate(self, messages, **kwargs):
                from app.core.llm import LLMResponse as CoreResp
                return CoreResp(content="ok", model="mock", tokens_used=1)
            async def stream(self, messages, **kwargs):
                yield "t"

        policy = RetryPolicy(max_attempts=1, strategy=RetryStrategy.FIXED, base_delay_s=0.0)
        gw     = LLMGateway(retry_policy=policy)
        gw.register("mock", MockProvider())
        engine = ExecutionEngine(gateway=gw, memory=BrokenMemory())
        result = await engine.run("test", session_id="s1")
        # Pipeline must complete despite memory failure
        assert not result.trace.error or "memory" in (result.trace.error or "").lower() or result.response


# ── TestDomainAgnosticism ─────────────────────────────────────────────────────

class TestDomainAgnosticism:
    """Memory components must contain zero domain-specific first-class fields."""

    TRADING_FIELDS = [
        "symbol", "stock", "candle", "rsi", "macd", "broker",
        "portfolio", "trade", "price", "market", "nifty",
        "signal", "indicator", "ticker",
    ]

    def test_memory_entry_has_no_trading_attributes(self):
        e = MemoryEntry()
        for attr in self.TRADING_FIELDS:
            assert attr not in vars(e), f"Domain attribute '{attr}' found on MemoryEntry"

    def test_short_term_memory_has_no_trading_attributes(self):
        stm = ShortTermMemory()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(stm, attr), f"Domain attribute '{attr}' found on ShortTermMemory"

    def test_long_term_memory_has_no_trading_attributes(self):
        ltm = InMemoryLongTermMemory()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(ltm, attr), f"Domain attribute '{attr}' found on InMemoryLongTermMemory"

    def test_embedding_service_has_no_trading_attributes(self):
        svc = SimpleEmbeddingService()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(svc, attr), f"Domain attribute '{attr}' found on SimpleEmbeddingService"

    def test_pipeline_provider_has_no_trading_attributes(self):
        p = MemoryPipelineProvider()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(p, attr), f"Domain attribute '{attr}' found on MemoryPipelineProvider"

    def test_metadata_carries_domain_data(self):
        """Domain data belongs in metadata, never as first-class fields."""
        e = MemoryEntry()
        e.metadata["symbol"]    = "RELIANCE"
        e.metadata["rsi_value"] = 72.4
        assert e.metadata["symbol"]    == "RELIANCE"
        assert e.metadata["rsi_value"] == 72.4
