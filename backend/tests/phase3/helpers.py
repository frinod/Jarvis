"""
Phase 3 Validation — Shared Helpers
======================================
Reusable utilities for assertions, result formatting, and reporting.
Imported by all test_*.py files. No fixtures here — only pure functions.

Rule: This file must stay under 300 lines.
"""
from __future__ import annotations
import time
from typing import Any, Dict, List, Optional, Tuple


# ── Result record ─────────────────────────────────────────────

class CheckResult:
    """Lightweight result object for a single validation check."""

    def __init__(self, name: str):
        self.name    = name
        self.passed  = False
        self.skipped = False
        self.detail  = ""
        self.source  = ""
        self.elapsed_ms: float = 0.0

    def ok(self, detail: str = "", source: str = "") -> "CheckResult":
        self.passed  = True
        self.detail  = detail
        self.source  = source
        return self

    def fail(self, detail: str) -> "CheckResult":
        self.passed = False
        self.detail = detail
        return self

    def skip(self, reason: str) -> "CheckResult":
        self.skipped = True
        self.detail  = reason
        return self

    def __repr__(self) -> str:
        icon = "✔" if self.passed else ("⚠" if self.skipped else "✘")
        src  = f" [{self.source}]" if self.source else ""
        ms   = f" {self.elapsed_ms}ms" if self.elapsed_ms else ""
        return f"  {icon} {self.name}{src}{ms} — {self.detail}"


# ── Candle helpers ────────────────────────────────────────────

def candle_count(result: Dict) -> int:
    return len(result.get("candles", []))


def source_of(result: Dict) -> str:
    return result.get("source", "unknown")


def is_angel_one(result: Dict) -> bool:
    return "angel" in source_of(result).lower()


def is_yahoo(result: Dict) -> bool:
    return "yahoo" in source_of(result).lower()


def candles_are_sorted(candles: List[Dict]) -> bool:
    """Return True if candles are in ascending timestamp order."""
    ts = [c["t"] for c in candles]
    return ts == sorted(ts)


def candles_have_no_duplicates(candles: List[Dict]) -> bool:
    ts = [c["t"] for c in candles]
    return len(ts) == len(set(ts))


def ohlcv_valid(candle: Dict) -> Tuple[bool, str]:
    """Return (valid, reason). Checks OHLCV integrity for one candle."""
    if candle["c"] <= 0:
        return False, f"close={candle['c']}"
    if candle["h"] < candle["l"]:
        return False, f"h={candle['h']} < l={candle['l']}"
    if candle["h"] < candle["c"] or candle["h"] < candle["o"]:
        return False, f"high not highest: h={candle['h']} o={candle['o']} c={candle['c']}"
    if candle["l"] > candle["c"] or candle["l"] > candle["o"]:
        return False, f"low not lowest: l={candle['l']} o={candle['o']} c={candle['c']}"
    return True, "ok"


def validate_all_candles(candles: List[Dict]) -> Tuple[int, List[str]]:
    """
    Validate every candle in a list.
    Returns (bad_count, list_of_error_messages).
    """
    errors = []
    for i, c in enumerate(candles):
        ok, reason = ohlcv_valid(c)
        if not ok:
            errors.append(f"candle[{i}] t={c.get('t')}: {reason}")
    return len(errors), errors


# ── Report printer ────────────────────────────────────────────

def print_section(title: str):
    bar = "─" * 56
    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)


def print_results(results: List[TestResult]):
    for r in results:
        print(repr(r))
    passed  = sum(1 for r in results if r.passed)
    skipped = sum(1 for r in results if r.skipped)
    failed  = sum(1 for r in results if not r.passed and not r.skipped)
    print(f"\n  Passed: {passed}  Skipped: {skipped}  Failed: {failed}")


def summarise(all_results: Dict[str, List[TestResult]]) -> Dict[str, int]:
    """Aggregate counts across all sections."""
    totals = {"passed": 0, "skipped": 0, "failed": 0}
    for section, results in all_results.items():
        totals["passed"]  += sum(1 for r in results if r.passed)
        totals["skipped"] += sum(1 for r in results if r.skipped)
        totals["failed"]  += sum(1 for r in results if not r.passed and not r.skipped)
    return totals


# ── Timing context manager ────────────────────────────────────

class Elapsed:
    """Simple elapsed-time context manager."""
    def __init__(self):
        self.ms: float = 0.0
    def __enter__(self):
        self._t = time.perf_counter()
        return self
    def __exit__(self, *_):
        self.ms = round((time.perf_counter() - self._t) * 1000, 1)
