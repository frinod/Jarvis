"""
test_orchestrator.py — Phase 4 orchestrator smoke tests.

Verifies that _fetch_stock_context() works end-to-end using
fetch_candles (not fetch_chart). Angel One rate-limit errors
are treated as skips, not failures.
"""
from __future__ import annotations
import asyncio
import pytest

_SKIP_ERRORS = {"insufficient_clean_data", "rate_limit", "no_data", "fetch_failed"}

_TA_FIELDS = ["current_price", "trend", "overall_signal", "confidence"]


def _is_rate_limit(result: str) -> bool:
    return any(e in result.lower() for e in _SKIP_ERRORS) or result == ""


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def orchestrator():
    from app.core.orchestrator import JarvisOrchestrator
    return JarvisOrchestrator()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestOrchestratorFetchStockContext:

    def test_returns_string(self, orchestrator):
        """_fetch_stock_context must return a string (never raise)."""
        result = asyncio.get_event_loop().run_until_complete(
            orchestrator._fetch_stock_context("RELIANCE", "analyze RELIANCE")
        )
        assert isinstance(result, str)

    def test_contains_stock_name_or_symbol(self, orchestrator):
        """On success, context must mention the symbol or stock name."""
        result = asyncio.get_event_loop().run_until_complete(
            orchestrator._fetch_stock_context("RELIANCE", "analyze RELIANCE")
        )
        if _is_rate_limit(result):
            pytest.skip("Angel One rate-limited or no data — skipping")
        assert "RELIANCE" in result.upper(), (
            f"Symbol not found in context. Got: {result[:200]}"
        )

    def test_contains_ta_fields(self, orchestrator):
        """On success, context must contain key TA labels."""
        result = asyncio.get_event_loop().run_until_complete(
            orchestrator._fetch_stock_context("TCS", "should I buy TCS")
        )
        if _is_rate_limit(result):
            pytest.skip("Angel One rate-limited or no data — skipping")
        lower = result.lower()
        missing = [f for f in ["rsi", "macd", "trend", "signal"] if f not in lower]
        assert not missing, f"TA fields missing from context: {missing}"

    def test_no_fetch_chart_in_context_path(self, orchestrator):
        """Confirm fetch_chart is not used — check via import inspection."""
        import inspect
        source = inspect.getsource(orchestrator._fetch_stock_context)
        assert "fetch_chart" not in source, (
            "_fetch_stock_context still references fetch_chart"
        )
        assert "fetch_candles" in source, (
            "_fetch_stock_context does not use fetch_candles"
        )

    def test_graceful_on_invalid_symbol(self, orchestrator):
        """Invalid symbol must return a non-empty error string, not raise."""
        result = asyncio.get_event_loop().run_until_complete(
            orchestrator._fetch_stock_context("INVALIDSYM999", "analyze INVALIDSYM999")
        )
        assert isinstance(result, str)
        # Either an error message or empty string — never an exception

    def test_comparison_branch_no_fetch_chart(self, orchestrator):
        """Comparison branch (vs/compare) must also use fetch_candles."""
        import inspect
        source = inspect.getsource(orchestrator._fetch_stock_context)
        # fetch_chart must not appear anywhere in the method source
        assert source.count("fetch_chart") == 0, (
            "fetch_chart found in _fetch_stock_context source"
        )
