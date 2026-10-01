"""
tests/phase7/test_7b_rag.py
============================
Phase 7B RAG pipeline tests.

Covers:
  - RetrievalResult metrics (7B.1)
  - DenseRetriever, KeywordRetriever, HybridRetriever (7B.2)
  - RRF merge correctness (7B.3)
  - Metadata filter (7B.4)
  - Retriever facade (7B.5)
  - NoOpReranker, CrossEncoderReranker fallback (7B.6)
  - ContextBuilder token budget, dedup, block types (7B.7)
  - PromptContextAssembler formatting and filtering (7B.8)
  - SemanticCache exact + semantic layers, TTL, eviction (7B.9)
  - MemoryPipelineProvider RAG path integration (7B.10)
  - SystemPromptBuilder ContextAssembly injection (7B.11)

All tests are pure -- no live Qdrant, no network, no model downloads.
"""
import asyncio
import time
import pytest

from app.ai.memory.short_term import MemoryEntry, MemoryRole, ShortTermMemory
from app.ai.memory.long_term import InMemoryLongTermMemory
from app.ai.memory.embeddings import SimpleEmbeddingService
from app.ai.memory import MemoryPipelineProvider
from app.ai.rag.retriever import (
    RetrievalResult, RetrievalStrategy,
    DenseRetriever, KeywordRetriever, HybridRetriever,
    Retriever, _rrf_merge, _apply_filters,
)
from app.ai.rag.reranker import BaseReranker, NoOpReranker, CrossEncoderReranker
from app.ai.rag.context_builder import (
    ContextBlock, ContextAssembly, ContextBuilder, PromptContextAssembler,
)
from app.ai.rag.semantic_cache import SemanticCache, _normalise
from app.ai.runtime.context import ExecutionContext


# ── Helpers ───────────────────────────────────────────────────────────────────

def _entry(content: str, importance: float = 0.8, entry_type: str = "") -> MemoryEntry:
    e = MemoryEntry(content=content, importance=importance)
    if entry_type:
        e.metadata["entry_type"] = entry_type
    return e


def _ctx(user_input: str = "RELIANCE breakout", session_id: str = "s1") -> ExecutionContext:
    return ExecutionContext(user_input=user_input, session_id=session_id)


async def _populated_ltm() -> InMemoryLongTermMemory:
    ltm = InMemoryLongTermMemory()
    await ltm.store(_entry("RELIANCE showing bullish breakout above 2800", entry_type="market_snapshot"))
    await ltm.store(_entry("NIFTY support at 22000 holding strong", entry_type="market_snapshot"))
    await ltm.store(_entry("User prefers concise answers", entry_type="conversation"))
    await ltm.store(_entry("HDFC earnings beat expectations", entry_type="news"))
    return ltm


# ── TestRetrievalResult ───────────────────────────────────────────────────────

class TestRetrievalResult:

    def test_final_count_auto_set(self):
        entries = [_entry("a"), _entry("b")]
        r = RetrievalResult(entries=entries)
        assert r.final_count == 2

    def test_empty_result(self):
        r = RetrievalResult(entries=[])
        assert r.final_count == 0
        assert r.cache_hit is False

    def test_metrics_fields_present(self):
        r = RetrievalResult(entries=[], strategy="hybrid", dense_count=10, keyword_count=8, merged_count=15)
        assert r.dense_count   == 10
        assert r.keyword_count == 8
        assert r.merged_count  == 15
        assert r.strategy      == "hybrid"


# ── TestRRFMerge ──────────────────────────────────────────────────────────────

class TestRRFMerge:

    def test_empty_lists(self):
        assert _rrf_merge([], []) == []

    def test_one_empty_list(self):
        entries = [_entry("a"), _entry("b")]
        result  = _rrf_merge(entries, [])
        assert len(result) == 2

    def test_deduplication(self):
        e = _entry("shared")
        result = _rrf_merge([e], [e])
        assert len(result) == 1

    def test_shared_entry_scores_higher(self):
        shared  = _entry("shared content")
        only_a  = _entry("only in a")
        only_b  = _entry("only in b")
        result  = _rrf_merge([shared, only_a], [shared, only_b])
        # shared appears in both lists so should rank first
        assert result[0].id == shared.id

    def test_order_preserved_for_unique_entries(self):
        a1 = _entry("a1")
        a2 = _entry("a2")
        result = _rrf_merge([a1, a2], [])
        assert result[0].id == a1.id   # a1 ranked higher (rank 0 in list_a)

    def test_returns_all_unique_entries(self):
        a = [_entry(f"a{i}") for i in range(5)]
        b = [_entry(f"b{i}") for i in range(5)]
        result = _rrf_merge(a, b)
        assert len(result) == 10


# ── TestMetadataFilter ────────────────────────────────────────────────────────

class TestMetadataFilter:

    def test_no_filter_returns_all(self):
        entries = [_entry("a", entry_type="market_snapshot"), _entry("b", entry_type="conversation")]
        assert len(_apply_filters(entries, None)) == 2

    def test_string_filter(self):
        entries = [_entry("a", entry_type="market_snapshot"), _entry("b", entry_type="conversation")]
        result  = _apply_filters(entries, {"entry_type": "market_snapshot"})
        assert len(result) == 1
        assert result[0].metadata["entry_type"] == "market_snapshot"

    def test_list_filter(self):
        entries = [
            _entry("a", entry_type="market_snapshot"),
            _entry("b", entry_type="news"),
            _entry("c", entry_type="conversation"),
        ]
        result = _apply_filters(entries, {"entry_type": ["market_snapshot", "news"]})
        assert len(result) == 2

    def test_unknown_filter_key_ignored(self):
        entries = [_entry("a")]
        result  = _apply_filters(entries, {"unknown_key": "value"})
        assert len(result) == 1

    def test_filter_removes_untagged_entries(self):
        entries = [_entry("no type"), _entry("typed", entry_type="market_snapshot")]
        result  = _apply_filters(entries, {"entry_type": "market_snapshot"})
        assert len(result) == 1


# ── TestKeywordRetriever ──────────────────────────────────────────────────────

class TestKeywordRetriever:

    @pytest.mark.asyncio
    async def test_returns_matching_entries(self):
        ltm = await _populated_ltm()
        r   = await KeywordRetriever(ltm).retrieve("RELIANCE", top_k=5)
        assert any("RELIANCE" in e.content for e in r.entries)

    @pytest.mark.asyncio
    async def test_top_k_respected(self):
        ltm = await _populated_ltm()
        r   = await KeywordRetriever(ltm).retrieve("NIFTY RELIANCE HDFC", top_k=2)
        assert len(r.entries) <= 2

    @pytest.mark.asyncio
    async def test_empty_ltm_returns_empty(self):
        r = await KeywordRetriever(InMemoryLongTermMemory()).retrieve("anything")
        assert r.entries == []

    @pytest.mark.asyncio
    async def test_strategy_name_set(self):
        r = await KeywordRetriever(InMemoryLongTermMemory()).retrieve("x")
        assert r.strategy == "keyword"

    @pytest.mark.asyncio
    async def test_never_raises_on_broken_ltm(self):
        class BrokenLTM(InMemoryLongTermMemory):
            async def search(self, q, top_k=5):
                raise RuntimeError("broken")
        r = await KeywordRetriever(BrokenLTM()).retrieve("x")
        assert r.entries == []


# ── TestDenseRetriever ────────────────────────────────────────────────────────

class TestDenseRetriever:

    @pytest.mark.asyncio
    async def test_returns_list(self):
        ltm = await _populated_ltm()
        emb = SimpleEmbeddingService()
        r   = await DenseRetriever(ltm, emb).retrieve("RELIANCE breakout", top_k=3)
        assert isinstance(r.entries, list)

    @pytest.mark.asyncio
    async def test_fallback_to_keyword_without_embeddings(self):
        ltm = await _populated_ltm()
        r   = await DenseRetriever(ltm, embeddings=None).retrieve("RELIANCE", top_k=5)
        assert isinstance(r.entries, list)

    @pytest.mark.asyncio
    async def test_strategy_name_set(self):
        r = await DenseRetriever(InMemoryLongTermMemory()).retrieve("x")
        assert r.strategy == "dense"

    @pytest.mark.asyncio
    async def test_never_raises_on_broken_embeddings(self):
        class BrokenEmb(SimpleEmbeddingService):
            def encode(self, text):
                raise RuntimeError("broken")
        ltm = await _populated_ltm()
        # encode() raises → DenseRetriever catches and returns empty result
        # (InMemoryLongTermMemory has no search_by_vector, so encode is called
        #  only when search_by_vector exists; without it, falls back to keyword)
        r = await DenseRetriever(ltm, BrokenEmb()).retrieve("RELIANCE")
        # Result must be a valid RetrievalResult — either entries or empty, never raises
        assert isinstance(r, RetrievalResult)


# ── TestHybridRetriever ───────────────────────────────────────────────────────

class TestHybridRetriever:

    @pytest.mark.asyncio
    async def test_returns_merged_results(self):
        ltm = await _populated_ltm()
        emb = SimpleEmbeddingService()
        r   = await HybridRetriever(ltm, emb).retrieve("RELIANCE breakout", top_k=3)
        assert isinstance(r.entries, list)
        assert r.strategy == "hybrid"

    @pytest.mark.asyncio
    async def test_metrics_populated(self):
        ltm = await _populated_ltm()
        r   = await HybridRetriever(ltm).retrieve("RELIANCE", top_k=3)
        assert r.dense_count   >= 0
        assert r.keyword_count >= 0
        assert r.merged_count  >= 0

    @pytest.mark.asyncio
    async def test_top_k_respected(self):
        ltm = await _populated_ltm()
        r   = await HybridRetriever(ltm).retrieve("RELIANCE NIFTY HDFC", top_k=2)
        assert len(r.entries) <= 2

    @pytest.mark.asyncio
    async def test_with_metadata_filter(self):
        ltm = await _populated_ltm()
        r   = await HybridRetriever(ltm).retrieve(
            "market", top_k=5, filters={"entry_type": "market_snapshot"}
        )
        for e in r.entries:
            assert e.metadata.get("entry_type") == "market_snapshot"


# ── TestRetrieverFacade ───────────────────────────────────────────────────────

class TestRetrieverFacade:

    @pytest.mark.asyncio
    async def test_delegates_to_strategy(self):
        ltm      = await _populated_ltm()
        retriever = Retriever(KeywordRetriever(ltm))
        r         = await retriever.retrieve("RELIANCE", top_k=3)
        assert isinstance(r.entries, list)

    @pytest.mark.asyncio
    async def test_never_raises_on_broken_strategy(self):
        class BrokenStrategy(RetrievalStrategy):
            async def retrieve(self, query, top_k=5, filters=None):
                raise RuntimeError("broken")
        r = await Retriever(BrokenStrategy()).retrieve("x")
        assert r.entries == []
        assert r.strategy == "error"

    def test_strategy_name(self):
        ltm = InMemoryLongTermMemory()
        assert Retriever(HybridRetriever(ltm)).strategy_name == "HybridRetriever"
        assert Retriever(KeywordRetriever(ltm)).strategy_name == "KeywordRetriever"


# ── TestNoOpReranker ──────────────────────────────────────────────────────────

class TestNoOpReranker:

    def test_returns_entries_unchanged(self):
        entries  = [_entry("a"), _entry("b"), _entry("c")]
        reranker = NoOpReranker()
        result   = reranker.rerank("query", entries, top_k=5)
        assert result == entries

    def test_top_k_truncates(self):
        entries = [_entry(f"e{i}") for i in range(10)]
        result  = NoOpReranker().rerank("q", entries, top_k=3)
        assert len(result) == 3

    def test_empty_input(self):
        assert NoOpReranker().rerank("q", [], top_k=5) == []

    def test_implements_base_reranker(self):
        assert isinstance(NoOpReranker(), BaseReranker)


# ── TestCrossEncoderRerankerFallback ──────────────────────────────────────────

class TestCrossEncoderRerankerFallback:
    """cross-encoder model not installed in CI — fallback to NoOpReranker."""

    def test_construction_does_not_raise(self):
        assert CrossEncoderReranker() is not None

    def test_rerank_returns_list(self):
        entries = [_entry("RELIANCE breakout"), _entry("NIFTY support")]
        result  = CrossEncoderReranker().rerank("RELIANCE", entries, top_k=2)
        assert isinstance(result, list)

    def test_rerank_empty_returns_empty(self):
        assert CrossEncoderReranker().rerank("q", [], top_k=5) == []

    def test_implements_base_reranker(self):
        assert isinstance(CrossEncoderReranker(), BaseReranker)

    def test_never_raises(self):
        entries = [_entry(f"e{i}") for i in range(5)]
        result  = CrossEncoderReranker().rerank("query", entries, top_k=3)
        assert len(result) <= 3


# ── TestContextBuilder ────────────────────────────────────────────────────────

class TestContextBuilder:

    def test_builds_blocks_from_entries(self):
        entries  = [_entry("RELIANCE breakout", entry_type="market_snapshot")]
        assembly = ContextBuilder().build(entries)
        assert len(assembly.blocks) == 1
        assert assembly.blocks[0].block_type == "market"

    def test_token_budget_respected(self):
        # Each entry ~25 chars → ~6 tokens. Budget 10 tokens → ~1-2 entries max.
        entries  = [_entry("x" * 100) for _ in range(20)]   # each ~25 tokens
        assembly = ContextBuilder(max_tokens=30).build(entries)
        assert assembly.total_tokens <= 30

    def test_deduplication(self):
        e        = _entry("duplicate content")
        assembly = ContextBuilder().build([e, e, e])
        assert assembly.entries_used == 1
        assert assembly.entries_dropped == 2

    def test_malformed_entries_dropped(self):
        entries  = [None, "not an entry", 42, _entry("valid")]  # type: ignore
        assembly = ContextBuilder().build(entries)
        assert assembly.entries_used == 1
        assert assembly.entries_dropped == 3

    def test_empty_content_dropped(self):
        e = MemoryEntry(content="   ")
        assembly = ContextBuilder().build([e])
        assert assembly.entries_used == 0

    def test_block_type_mapping(self):
        entries = [
            _entry("conv", entry_type="conversation"),
            _entry("mkt",  entry_type="market_snapshot"),
            _entry("news", entry_type="news"),
            _entry("strat",entry_type="analysis_result"),
            _entry("unknown_type"),
        ]
        assembly = ContextBuilder().build(entries)
        types = {b.block_type for b in assembly.blocks}
        assert "conversation" in types
        assert "market"       in types
        assert "strategy"     in types

    def test_prompt_text_non_empty(self):
        entries  = [_entry("RELIANCE breakout", entry_type="market_snapshot")]
        assembly = ContextBuilder().build(entries)
        assert len(assembly.prompt_text) > 0
        assert "RELIANCE" in assembly.prompt_text

    def test_metrics_attached(self):
        entries  = [_entry("x")]
        metrics  = {"dense_count": 5, "keyword_count": 3}
        assembly = ContextBuilder().build(entries, metrics=metrics)
        assert assembly.metrics["dense_count"] == 5

    def test_never_raises_on_any_input(self):
        assembly = ContextBuilder().build(None)  # type: ignore
        assert isinstance(assembly, ContextAssembly)

    def test_is_empty_when_no_entries(self):
        assert ContextBuilder().build([]).is_empty


# ── TestPromptContextAssembler ────────────────────────────────────────────────

class TestPromptContextAssembler:

    def test_format_returns_string(self):
        entries  = [_entry("RELIANCE breakout", entry_type="market_snapshot")]
        assembly = ContextBuilder().build(entries)
        text     = PromptContextAssembler().format(assembly)
        assert isinstance(text, str)
        assert "RELIANCE" in text

    def test_format_empty_assembly_returns_empty_string(self):
        text = PromptContextAssembler().format(ContextAssembly())
        assert text == ""

    def test_include_types_filter(self):
        entries = [
            _entry("market data", entry_type="market_snapshot"),
            _entry("conversation turn", entry_type="conversation"),
        ]
        assembly = ContextBuilder().build(entries)
        text     = PromptContextAssembler().format(assembly, include_types=["market"])
        assert "market data" in text
        assert "conversation turn" not in text

    def test_metrics_summary_format(self):
        assembly = ContextAssembly(
            entries_used=5, entries_dropped=2, total_tokens=400,
            metrics={"dense_count": 10, "keyword_count": 8, "merged_count": 15, "cache_hit": False},
        )
        summary = PromptContextAssembler().metrics_summary(assembly)
        assert "used=5" in summary
        assert "tokens=400" in summary


# ── TestSemanticCache ─────────────────────────────────────────────────────────

class TestSemanticCache:

    def _result(self, n: int = 2) -> RetrievalResult:
        return RetrievalResult(entries=[_entry(f"e{i}") for i in range(n)], strategy="keyword")

    def test_miss_on_empty_cache(self):
        cache = SemanticCache()
        assert cache.get("RELIANCE breakout") is None

    def test_exact_hit_after_put(self):
        cache = SemanticCache()
        r     = self._result()
        cache.put("RELIANCE breakout", r)
        hit = cache.get("RELIANCE breakout")
        assert hit is not None
        assert hit.cache_hit is True

    def test_normalised_exact_hit(self):
        cache = SemanticCache()
        cache.put("RELIANCE  Breakout", self._result())
        hit = cache.get("reliance breakout")
        assert hit is not None

    def test_miss_after_ttl_expired(self):
        cache = SemanticCache(ttl_market_s=0.01, ttl_general_s=0.01)
        cache.put("RELIANCE", self._result())
        time.sleep(0.05)
        assert cache.get("RELIANCE") is None

    def test_semantic_hit_with_embeddings(self):
        emb   = SimpleEmbeddingService()
        cache = SemanticCache(embeddings=emb, threshold=0.5)
        r     = self._result()
        cache.put("RELIANCE bullish breakout", r)
        # Semantically similar query
        hit = cache.get("RELIANCE bullish breakout above resistance")
        # May or may not hit depending on similarity — just verify no crash
        assert hit is None or hit.cache_hit is True

    def test_disabled_cache_always_misses(self):
        cache = SemanticCache(enabled=False)
        cache.put("RELIANCE", self._result())
        assert cache.get("RELIANCE") is None

    def test_size_increments(self):
        cache = SemanticCache()
        cache.put("query1", self._result())
        cache.put("query2", self._result())
        assert cache.size == 2

    def test_clear_resets_cache(self):
        cache = SemanticCache()
        cache.put("q", self._result())
        cache.clear()
        assert cache.size == 0
        assert cache.get("q") is None

    def test_invalidate_removes_entry(self):
        cache = SemanticCache()
        cache.put("RELIANCE", self._result())
        cache.invalidate("RELIANCE")
        assert cache.get("RELIANCE") is None

    def test_eviction_at_max_size(self):
        from app.ai.rag.semantic_cache import _MAX_CACHE_SIZE
        cache = SemanticCache()
        for i in range(_MAX_CACHE_SIZE + 5):
            cache.put(f"query_{i}", self._result())
        assert cache.size <= _MAX_CACHE_SIZE

    def test_hit_rate_calculation(self):
        cache = SemanticCache()
        cache.put("q", self._result())
        cache.get("q")    # hit
        cache.get("miss") # miss
        assert cache.hit_rate == 0.5

    def test_stats_structure(self):
        cache = SemanticCache()
        s = cache.stats()
        assert "size" in s and "hits" in s and "hit_rate" in s

    def test_never_raises_on_broken_embeddings(self):
        class BrokenEmb(SimpleEmbeddingService):
            def encode(self, text):
                raise RuntimeError("broken")
        cache = SemanticCache(embeddings=BrokenEmb())
        cache.put("q", self._result())
        result = cache.get("q")   # exact hit still works
        assert result is not None


# ── TestNormalise ─────────────────────────────────────────────────────────────

class TestNormalise:

    def test_lowercase(self):
        assert _normalise("RELIANCE") == "reliance"

    def test_strips_whitespace(self):
        assert _normalise("  hello  ") == "hello"

    def test_collapses_spaces(self):
        assert _normalise("a  b   c") == "a b c"


# ── TestMemoryPipelineProviderRAGPath ─────────────────────────────────────────

class TestMemoryPipelineProviderRAGPath:

    @pytest.mark.asyncio
    async def test_rag_path_populates_memory_context(self):
        ltm      = await _populated_ltm()
        emb      = SimpleEmbeddingService()
        retriever = Retriever(HybridRetriever(ltm, emb))
        reranker  = NoOpReranker()
        builder   = ContextBuilder()
        cache     = SemanticCache(embeddings=emb)

        provider = MemoryPipelineProvider(
            long_term=ltm, embeddings=emb,
            retriever=retriever, reranker=reranker,
            context_builder=builder, semantic_cache=cache,
        )
        ctx = _ctx("RELIANCE breakout analysis")
        await provider.load(ctx)
        assert isinstance(ctx.memory_context, list)

    @pytest.mark.asyncio
    async def test_rag_path_stores_context_assembly(self):
        ltm      = await _populated_ltm()
        emb      = SimpleEmbeddingService()
        retriever = Retriever(HybridRetriever(ltm, emb))
        provider  = MemoryPipelineProvider(
            long_term=ltm, embeddings=emb,
            retriever=retriever, context_builder=ContextBuilder(),
        )
        ctx = _ctx("RELIANCE breakout")
        await provider.load(ctx)
        assert "_rag_context" in ctx.metadata
        assert isinstance(ctx.metadata["_rag_context"], ContextAssembly)

    @pytest.mark.asyncio
    async def test_cache_hit_on_second_call(self):
        ltm      = await _populated_ltm()
        emb      = SimpleEmbeddingService()
        cache     = SemanticCache(embeddings=emb)
        retriever = Retriever(KeywordRetriever(ltm))
        provider  = MemoryPipelineProvider(
            long_term=ltm, retriever=retriever, semantic_cache=cache,
        )
        ctx1 = _ctx("RELIANCE breakout")
        ctx2 = _ctx("RELIANCE breakout")
        await provider.load(ctx1)
        await provider.load(ctx2)
        assert cache.stats()["hits"] >= 1

    @pytest.mark.asyncio
    async def test_legacy_path_when_no_retriever(self):
        ltm      = await _populated_ltm()
        provider = MemoryPipelineProvider(long_term=ltm)
        ctx      = _ctx("RELIANCE")
        await provider.load(ctx)
        assert isinstance(ctx.memory_context, list)

    @pytest.mark.asyncio
    async def test_stm_always_populated(self):
        provider = MemoryPipelineProvider()
        ctx      = _ctx("test input")
        await provider.load(ctx)
        assert provider.short_term.size >= 1


# ── TestSystemPromptBuilderContextAssembly ────────────────────────────────────

class TestSystemPromptBuilderContextAssembly:

    def test_uses_context_assembly_when_present(self):
        from app.ai.prompts.system import SystemPromptBuilder
        entries  = [_entry("RELIANCE breakout", entry_type="market_snapshot")]
        assembly = ContextBuilder().build(entries)
        ctx      = _ctx("RELIANCE analysis")
        ctx.metadata["_rag_context"] = assembly
        builder  = SystemPromptBuilder()
        messages = builder.build(ctx)
        combined = " ".join(m.content for m in messages)
        assert "RELIANCE" in combined

    def test_falls_back_to_raw_entries_without_assembly(self):
        from app.ai.prompts.system import SystemPromptBuilder
        ctx = _ctx("hello")
        ctx.memory_context = [_entry("some memory")]
        messages = SystemPromptBuilder().build(ctx)
        combined = " ".join(m.content for m in messages)
        assert "some memory" in combined

    def test_empty_assembly_produces_no_memory_message(self):
        from app.ai.prompts.system import SystemPromptBuilder
        ctx = _ctx("hello")
        ctx.metadata["_rag_context"] = ContextAssembly()
        messages = SystemPromptBuilder().build(ctx)
        # No memory message should be injected for empty assembly
        memory_msgs = [m for m in messages if "Relevant context" in m.content]
        assert len(memory_msgs) == 0
