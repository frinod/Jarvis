"""
test_dead_code.py — Phase 4 AST validation.

Asserts:
  1. Zero fetch_chart Name/Attribute nodes in all 11 migrated modules.
  2. fetch_chart function definition removed from stock_fetcher.py.
  3. orchestrator.py imports fetch_candles (not fetch_chart).
  4. stock_data.py does not re-export fetch_chart.
"""
from __future__ import annotations
import ast
import os
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ast_names(path: str) -> set:
    """Return all Name and Attribute id/attr strings in the AST of a file."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()
    tree = ast.parse(source, filename=path)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _has_funcdef(path: str, func_name: str) -> bool:
    """Return True if the file contains a top-level function definition with func_name."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()
    tree = ast.parse(source, filename=path)
    return any(
        isinstance(node, ast.FunctionDef) and node.name == func_name
        for node in ast.walk(tree)
    )


def _import_names(path: str) -> set:
    """Return all names imported in the file (from x import a, b -> {a, b})."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()
    tree = ast.parse(source, filename=path)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestDeadCode:

    def test_no_fetch_chart_calls_in_migrated_modules(self, migrated_modules):
        """All 11 migrated modules must have zero fetch_chart Name/Attribute nodes."""
        violations = []
        for path in migrated_modules:
            assert os.path.exists(path), f"File not found: {path}"
            names = _ast_names(path)
            if "fetch_chart" in names:
                violations.append(os.path.basename(path))
        assert not violations, (
            f"fetch_chart still referenced in: {violations}"
        )

    def test_fetch_chart_removed_from_stock_fetcher(self, backend_root):
        """fetch_chart function definition must be gone from stock_fetcher.py."""
        path = os.path.join(backend_root, "app", "api", "stock_fetcher.py")
        assert os.path.exists(path)
        assert not _has_funcdef(path, "fetch_chart"), (
            "fetch_chart function definition still present in stock_fetcher.py"
        )

    def test_orchestrator_imports_fetch_candles(self, backend_root):
        """orchestrator.py must import fetch_candles (inline import inside method)."""
        path = os.path.join(backend_root, "app", "core", "orchestrator.py")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        assert "fetch_candles" in source, (
            "orchestrator.py does not reference fetch_candles"
        )
        assert "from app.api.stock_fetcher import fetch_chart" not in source, (
            "orchestrator.py still imports fetch_chart from stock_fetcher"
        )

    def test_stock_data_no_fetch_chart_export(self, backend_root):
        """stock_data.py must not re-export fetch_chart."""
        path = os.path.join(backend_root, "app", "api", "stock_data.py")
        imported = _import_names(path)
        assert "fetch_chart" not in imported, (
            "stock_data.py still imports/re-exports fetch_chart"
        )

    def test_stock_fetcher_still_exports_required_names(self, backend_root):
        """stock_fetcher.py must still export HEADERS, fetch_quote, fetch_index, get_all_stocks."""
        path = os.path.join(backend_root, "app", "api", "stock_fetcher.py")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        for name in ("HEADERS", "fetch_quote", "fetch_index", "get_all_stocks"):
            assert name in source, f"stock_fetcher.py missing required export: {name}"

    def test_architecture_diagram_updated(self, backend_root):
        """orchestrator.py diagram must reference market_data.service, not Yahoo Finance alone."""
        path = os.path.join(backend_root, "app", "core", "orchestrator.py")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        assert "market_data.service" in source, (
            "Architecture diagram not updated — market_data.service not mentioned"
        )
