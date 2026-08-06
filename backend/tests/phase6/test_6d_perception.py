"""
tests/phase6/test_6d_perception.py
=====================================
Unit tests for Perception package (Tasks 6D.8–6D.10).

Covers: PerceptionBundle, MarketPerception, NewsItem, NewsPerception,
        SentimentScore, SentimentPerception.
"""
import pytest

from app.ai.perception.market import (
    MarketPerception, InMemoryMarketPerception, PerceptionBundle,
)
from app.ai.perception.news import (
    NewsPerception, InMemoryNewsPerception, NewsItem,
)
from app.ai.perception.sentiment import (
    SentimentPerception, InMemorySentimentPerception, SentimentScore,
)


# ── TestPerceptionBundle ──────────────────────────────────────────────────────

class TestPerceptionBundle:

    def test_construction(self):
        b = PerceptionBundle(source="test", data={"price": 100.0})
        assert b.source  == "test"
        assert b.data    == {"price": 100.0}
        assert b.success is True

    def test_error_field(self):
        b = PerceptionBundle(source="test", data={}, success=False, error="unavailable")
        assert b.error == "unavailable"

    def test_timestamp_auto_set(self):
        b = PerceptionBundle(source="test", data={})
        assert b.timestamp > 0


# ── TestInMemoryMarketPerception ──────────────────────────────────────────────

class TestInMemoryMarketPerception:

    @pytest.mark.asyncio
    async def test_fetch_returns_bundle(self):
        p      = InMemoryMarketPerception()
        bundle = await p.fetch({})
        assert isinstance(bundle, PerceptionBundle)

    @pytest.mark.asyncio
    async def test_fetch_includes_mock_data(self):
        p      = InMemoryMarketPerception(mock_data={"price": 150.0})
        bundle = await p.fetch({})
        assert bundle.data["price"] == 150.0

    @pytest.mark.asyncio
    async def test_fetch_merges_params(self):
        p      = InMemoryMarketPerception(mock_data={"price": 100.0})
        bundle = await p.fetch({"symbol": "TEST"})
        assert bundle.data["symbol"] == "TEST"
        assert bundle.data["price"]  == 100.0

    @pytest.mark.asyncio
    async def test_is_available_true_by_default(self):
        p = InMemoryMarketPerception()
        assert await p.is_available() is True

    @pytest.mark.asyncio
    async def test_set_unavailable(self):
        p = InMemoryMarketPerception()
        p.set_available(False)
        assert await p.is_available() is False

    @pytest.mark.asyncio
    async def test_unavailable_returns_failed_bundle(self):
        p = InMemoryMarketPerception()
        p.set_available(False)
        bundle = await p.fetch({})
        assert bundle.success is False
        assert bundle.error   is not None

    def test_set_mock_data(self):
        p = InMemoryMarketPerception()
        p.set_mock_data({"volume": 9999})
        assert p._mock_data["volume"] == 9999

    def test_is_abc_subclass(self):
        p = InMemoryMarketPerception()
        assert isinstance(p, MarketPerception)


# ── TestNewsItem ──────────────────────────────────────────────────────────────

class TestNewsItem:

    def test_construction(self):
        item = NewsItem(title="Market Update", summary="Prices rose today.")
        assert item.title   == "Market Update"
        assert item.summary == "Prices rose today."

    def test_sentiment_default_zero(self):
        item = NewsItem(title="test")
        assert item.sentiment == 0.0

    def test_timestamp_auto_set(self):
        item = NewsItem(title="test")
        assert item.timestamp > 0

    def test_metadata_default_empty(self):
        item = NewsItem(title="test")
        assert item.metadata == {}


# ── TestInMemoryNewsPerception ────────────────────────────────────────────────

class TestInMemoryNewsPerception:

    @pytest.mark.asyncio
    async def test_fetch_returns_list(self):
        p     = InMemoryNewsPerception()
        items = await p.fetch({})
        assert isinstance(items, list)

    @pytest.mark.asyncio
    async def test_fetch_returns_mock_items(self):
        items = [NewsItem(title="headline 1"), NewsItem(title="headline 2")]
        p     = InMemoryNewsPerception(mock_items=items)
        result = await p.fetch({})
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_fetch_respects_limit(self):
        items = [NewsItem(title=f"item {i}") for i in range(10)]
        p     = InMemoryNewsPerception(mock_items=items)
        result = await p.fetch({"limit": 3})
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_unavailable_returns_empty(self):
        items = [NewsItem(title="test")]
        p     = InMemoryNewsPerception(mock_items=items)
        p.set_available(False)
        result = await p.fetch({})
        assert result == []

    @pytest.mark.asyncio
    async def test_is_available_true_by_default(self):
        p = InMemoryNewsPerception()
        assert await p.is_available() is True

    def test_add_item(self):
        p = InMemoryNewsPerception()
        p.add_item(NewsItem(title="new item"))
        assert len(p._items) == 1

    def test_is_abc_subclass(self):
        p = InMemoryNewsPerception()
        assert isinstance(p, NewsPerception)


# ── TestSentimentScore ────────────────────────────────────────────────────────

class TestSentimentScore:

    def test_positive_label(self):
        s = SentimentScore.from_score(0.5)
        assert s.label == "positive"

    def test_negative_label(self):
        s = SentimentScore.from_score(-0.5)
        assert s.label == "negative"

    def test_neutral_label(self):
        s = SentimentScore.from_score(0.0)
        assert s.label == "neutral"

    def test_score_rounded(self):
        s = SentimentScore.from_score(0.12345)
        assert s.score == round(0.12345, 3)

    def test_sample_size(self):
        s = SentimentScore.from_score(0.5, sample_size=10)
        assert s.sample_size == 10


# ── TestInMemorySentimentPerception ──────────────────────────────────────────

class TestInMemorySentimentPerception:

    @pytest.mark.asyncio
    async def test_score_empty_returns_neutral(self):
        p      = InMemorySentimentPerception()
        result = await p.score({})
        assert result.score == 0.0
        assert result.label == "neutral"

    @pytest.mark.asyncio
    async def test_score_positive_items(self):
        items = [
            NewsItem(title="good news", sentiment=0.8),
            NewsItem(title="great news", sentiment=0.9),
        ]
        p      = InMemorySentimentPerception(news_items=items)
        result = await p.score({})
        assert result.score > 0.0
        assert result.label == "positive"

    @pytest.mark.asyncio
    async def test_score_negative_items(self):
        items = [
            NewsItem(title="bad news", sentiment=-0.7),
            NewsItem(title="worse news", sentiment=-0.8),
        ]
        p      = InMemorySentimentPerception(news_items=items)
        result = await p.score({})
        assert result.score < 0.0
        assert result.label == "negative"

    @pytest.mark.asyncio
    async def test_score_clamped_to_range(self):
        items = [NewsItem(title="x", sentiment=2.0)]   # out of range
        p     = InMemorySentimentPerception(news_items=items)
        result = await p.score({})
        assert -1.0 <= result.score <= 1.0

    @pytest.mark.asyncio
    async def test_sample_size_matches_item_count(self):
        items = [NewsItem(title=f"item {i}", sentiment=0.5) for i in range(5)]
        p     = InMemorySentimentPerception(news_items=items)
        result = await p.score({})
        assert result.sample_size == 5

    @pytest.mark.asyncio
    async def test_is_available_true_by_default(self):
        p = InMemorySentimentPerception()
        assert await p.is_available() is True

    def test_set_items(self):
        p = InMemorySentimentPerception()
        p.set_items([NewsItem(title="x")])
        assert len(p._items) == 1

    def test_is_abc_subclass(self):
        p = InMemorySentimentPerception()
        assert isinstance(p, SentimentPerception)
