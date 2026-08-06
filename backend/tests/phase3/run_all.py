"""
Phase 3 Validation — Test Runner
==================================
Runs all Phase 3 validation tests via pytest and prints
a structured completion report.

Usage:
    cd backend
    python tests/phase3/run_all.py

Or via pytest directly:
    pytest tests/phase3/ -v --tb=short

Rule: This file must stay under 300 lines.
"""
from __future__ import annotations
import os
import sys
import subprocess
import time

# ── Path bootstrap ────────────────────────────────────────────
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def _bar(char: str = "─", width: int = 58) -> str:
    return char * width


def _header():
    print(_bar("═"))
    print("  JARVIS Phase 3 Validation Suite")
    print("  Market Data Architecture — Full Verification")
    print(_bar("═"))
    print()


def _section_plan():
    plan = [
        ("conftest.py",         "Fixtures & shared setup"),
        ("helpers.py",          "Utilities & formatters"),
        ("test_providers.py",   "Provider registration, auth, cache"),
        ("test_modules.py",     "All 9 migrated modules functional"),
        ("test_consistency.py", "Data consistency across modules"),
        ("test_dead_code.py",   "Dead code audit (AST scan)"),
        ("test_performance.py", "Latency, cache hit rate, concurrency"),
    ]
    print("  Test Files:")
    for fname, desc in plan:
        print(f"    {fname:<30} {desc}")
    print()


def _run_pytest() -> int:
    """Run pytest on the phase3 directory. Returns exit code."""
    test_dir = os.path.join(_BACKEND, "tests", "phase3")
    cmd = [
        sys.executable, "-m", "pytest",
        test_dir,
        "-v",
        "--tb=short",
        "--no-header",
        "-p", "no:warnings",
        "--asyncio-mode=auto",
    ]
    print(_bar())
    print("  Running pytest...")
    print(_bar())
    print()

    start = time.perf_counter()
    result = subprocess.run(cmd, cwd=_BACKEND)
    elapsed = round(time.perf_counter() - start, 1)

    print()
    print(_bar())
    print(f"  Total time: {elapsed}s")
    return result.returncode


def _dependency_graph():
    """Print the verified dependency graph."""
    print()
    print(_bar())
    print("  Dependency Graph (verified)")
    print(_bar())
    graph = (
        "  Frontend (Next.js :3000)\n"
        "        |\n"
        "        v\n"
        "  routes.py  (FastAPI :8000)\n"
        "        |\n"
        "        v\n"
        "  market_data/service.py   <-- single entry point\n"
        "        |\n"
        "        v\n"
        "  ProviderManager\n"
        "        |\n"
        "        +-- AngelOneProvider  (priority 10)  <-- PRIMARY\n"
        "        |       |\n"
        "        |       +-- angel_auth.py (JWT session)\n"
        "        |\n"
        "        +-- YahooFinanceProvider (priority 90) <-- FALLBACK\n"
        "\n"
        "  Modules using service.fetch_candles():\n"
        "    forecaster.py       market_regime.py    mtf_analysis.py\n"
        "    market_intelligence budget_advisor.py   auto_trader.py\n"
        "    backtesting.py      paper_trading.py    routes.py\n"
        "\n"
        "  Known Phase 4 targets (still use shim):\n"
        "    orchestrator.py     stock_data.py (re-export only)\n"
    )
    print(graph)


def _phase4_targets():
    """Print what remains for Phase 4."""
    print(_bar())
    print("  Phase 4 Targets (not yet migrated)")
    print(_bar())
    targets = [
        ("orchestrator.py",  "_fetch_stock_context()",  "2 fetch_chart calls"),
        ("stock_data.py",    "re-export line",           "import cleanup only"),
        ("stock_fetcher.py", "fetch_chart() definition", "remove after Phase 4"),
    ]
    for fname, location, note in targets:
        print(f"    {fname:<22} {location:<28} {note}")
    print()


def main():
    _header()
    _section_plan()
    exit_code = _run_pytest()
    _dependency_graph()
    _phase4_targets()

    print(_bar("═"))
    if exit_code == 0:
        print("  PHASE 3 VALIDATION: PASSED")
        print("  System is stable. Ready for Phase 4 approval.")
    else:
        print("  PHASE 3 VALIDATION: FAILURES DETECTED")
        print("  Review output above before proceeding to Phase 4.")
    print(_bar("═"))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
