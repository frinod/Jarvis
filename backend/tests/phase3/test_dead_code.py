"""
Phase 3 Validation — Dead Code Audit
======================================
Verifies that fetch_chart() from stock_fetcher is no longer
called by any migrated module. Also audits the orchestrator
as a known remaining caller that needs Phase 4 migration.

Rule: This file must stay under 300 lines.
"""
from __future__ import annotations
import ast
import os
from pathlib import Path
from typing import List, Tuple

import pytest

from tests.phase3.helpers import CheckResult, print_section, print_results

_API_DIR = Path(__file__).parent.parent.parent / "app" / "api"
_CORE_DIR = Path(__file__).parent.parent.parent / "app" / "core"

# Modules that were migrated in Phase 2 & 3 — must NOT call fetch_chart
_MIGRATED = [
    "forecaster.py",
    "mtf_analysis.py",
    "market_intelligence.py",
    "market_regime.py",
    "budget_advisor.py",
    "auto_trader.py",
    "backtesting.py",
    "paper_trading.py",
    "routes.py",
]

# Known remaining callers — not yet migrated (Phase 4 work)
_KNOWN_REMAINING = {
    "stock_fetcher.py",   # shim definition — expected
    "stock_data.py",      # re-export — expected
    "orchestrator.py",    # Phase 4 target — documented
}


def _find_fetch_chart_calls(filepath: Path) -> List[int]:
    """
    Parse a Python file and return line numbers where
    fetch_chart is called or imported from stock_fetcher.
    """
    try:
        source = filepath.read_text(encoding="utf-8")
        tree   = ast.parse(source)
    except Exception:
        return []

    lines = []
    for node in ast.walk(tree):
        # Import: from app.api.stock_fetcher import fetch_chart
        if isinstance(node, ast.ImportFrom):
            if node.module and "stock_fetcher" in node.module:
                for alias in node.names:
                    if alias.name == "fetch_chart":
                        lines.append(node.lineno)
        # Call: fetch_chart(...)
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "fetch_chart":
                lines.append(node.lineno)
            if isinstance(func, ast.Attribute) and func.attr == "fetch_chart":
                lines.append(node.lineno)
    return lines


# ── 5.1 Migrated modules are clean ───────────────────────────

def test_migrated_modules_no_fetch_chart():
    """All Phase 2/3 migrated modules must have zero fetch_chart references."""
    print_section("5.1 Dead Code — Migrated Modules")
    results = []

    for filename in _MIGRATED:
        path = _API_DIR / filename
        if not path.exists():
            r = CheckResult(filename)
            r.skip(f"file not found: {path}")
            results.append(r)
            continue

        hits = _find_fetch_chart_calls(path)
        r = CheckResult(filename)
        if not hits:
            r.ok("no fetch_chart references")
        else:
            r.fail(f"fetch_chart found at lines: {hits}")
        results.append(r)

    print_results(results)
    failures = [r for r in results if not r.passed and not r.skipped]
    assert not failures, (
        f"fetch_chart still present in migrated modules: "
        f"{[r.name for r in failures]}"
    )


# ── 5.2 Known remaining callers are documented ───────────────

def test_known_remaining_callers_documented():
    """
    stock_fetcher.py, stock_data.py, orchestrator.py are known
    remaining callers. This test documents them and confirms
    no NEW unexpected callers have appeared.
    """
    print_section("5.2 Dead Code — Known Remaining Callers")
    results = []

    all_py = list(_API_DIR.glob("*.py")) + list(_CORE_DIR.glob("*.py"))
    unexpected = []

    for path in all_py:
        if path.name in _KNOWN_REMAINING:
            hits = _find_fetch_chart_calls(path)
            r = CheckResult(path.name)
            if hits:
                r.skip(f"known remaining caller — lines {hits} (Phase 4 target)")
            else:
                r.ok("no fetch_chart (already clean)")
            results.append(r)
        else:
            hits = _find_fetch_chart_calls(path)
            if hits:
                unexpected.append((path.name, hits))

    if unexpected:
        r = CheckResult("no_unexpected_callers")
        r.fail(f"unexpected fetch_chart callers: {unexpected}")
        results.append(r)
    else:
        r = CheckResult("no_unexpected_callers")
        r.ok("no unexpected callers found")
        results.append(r)

    print_results(results)
    assert not unexpected, (
        f"Unexpected fetch_chart callers found: {unexpected}. "
        f"These must be migrated or added to _KNOWN_REMAINING."
    )


# ── 5.3 service.fetch_candles is the active import ───────────

def test_migrated_modules_import_service():
    """Migrated modules must import fetch_candles from market_data.service."""
    print_section("5.3 Service Import Verification")
    results = []

    # Subset that directly call fetch_candles (not via sub-calls)
    direct_callers = [
        "forecaster.py", "mtf_analysis.py", "market_regime.py",
        "budget_advisor.py", "backtesting.py", "paper_trading.py",
    ]

    for filename in direct_callers:
        path = _API_DIR / filename
        if not path.exists():
            results.append(CheckResult(filename).skip("file not found"))
            continue

        source = path.read_text(encoding="utf-8")
        has_service_import = "market_data.service" in source and "fetch_candles" in source

        r = CheckResult(filename)
        if has_service_import:
            r.ok("imports from market_data.service")
        else:
            r.fail("does not import fetch_candles from market_data.service")
        results.append(r)

    print_results(results)
    failures = [r for r in results if not r.passed and not r.skipped]
    assert not failures, f"Missing service imports: {[r.name for r in failures]}"
