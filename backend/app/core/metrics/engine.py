"""
core/metrics/engine.py
======================
Metrics Engine for the JARVIS Kernel.

In-process counters, gauges, and histograms.
No external dependency -- pure Python.
Designed to be scraped by Prometheus or logged periodically.

Design principles
-----------------
  Three instrument types: Counter, Gauge, Histogram
  Named + labelled -- metrics identified by name + label dict
  Thread-safe reads -- snapshot() returns a copy
  No external dependency -- stdlib only
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Counter:
    """Monotonically increasing counter."""
    name:   str
    labels: Dict[str, str] = field(default_factory=dict)
    value:  float = 0.0

    def inc(self, amount: float = 1.0) -> None:
        if amount < 0:
            raise ValueError("Counter can only be incremented")
        self.value += amount

    def to_dict(self) -> dict:
        return {"name": self.name, "type": "counter",
                "value": self.value, "labels": self.labels}


@dataclass
class Gauge:
    """Gauge that can go up or down."""
    name:   str
    labels: Dict[str, str] = field(default_factory=dict)
    value:  float = 0.0

    def set(self, value: float) -> None:
        self.value = value

    def inc(self, amount: float = 1.0) -> None:
        self.value += amount

    def dec(self, amount: float = 1.0) -> None:
        self.value -= amount

    def to_dict(self) -> dict:
        return {"name": self.name, "type": "gauge",
                "value": self.value, "labels": self.labels}


@dataclass
class Histogram:
    """Tracks distribution of observed values."""
    name:    str
    labels:  Dict[str, str] = field(default_factory=dict)
    _values: List[float]    = field(default_factory=list, repr=False)

    def observe(self, value: float) -> None:
        self._values.append(value)

    @property
    def count(self) -> int:
        return len(self._values)

    @property
    def sum(self) -> float:
        return sum(self._values)

    @property
    def mean(self) -> float:
        return self.sum / self.count if self._values else 0.0

    def percentile(self, p: float) -> float:
        """Return the p-th percentile (0-100)."""
        if not self._values:
            return 0.0
        sorted_vals = sorted(self._values)
        idx = int(len(sorted_vals) * p / 100)
        idx = min(idx, len(sorted_vals) - 1)
        return sorted_vals[idx]

    def to_dict(self) -> dict:
        return {
            "name":   self.name,
            "type":   "histogram",
            "count":  self.count,
            "sum":    self.sum,
            "mean":   round(self.mean, 6),
            "p50":    self.percentile(50),
            "p95":    self.percentile(95),
            "p99":    self.percentile(99),
            "labels": self.labels,
        }


class MetricsEngine:
    """
    In-process metrics registry.

    Usage
    -----
        metrics = MetricsEngine()

        # Counter
        metrics.counter("api_requests", labels={"endpoint": "/quote"}).inc()

        # Gauge
        metrics.gauge("open_positions").set(5)

        # Histogram
        metrics.histogram("response_time_s").observe(0.042)

        # Snapshot
        snap = metrics.snapshot()
    """

    def __init__(self) -> None:
        self._counters:   Dict[str, Counter]   = {}
        self._gauges:     Dict[str, Gauge]      = {}
        self._histograms: Dict[str, Histogram]  = {}

    def counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> Counter:
        key = self._key(name, labels)
        if key not in self._counters:
            self._counters[key] = Counter(name=name, labels=labels or {})
        return self._counters[key]

    def gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> Gauge:
        key = self._key(name, labels)
        if key not in self._gauges:
            self._gauges[key] = Gauge(name=name, labels=labels or {})
        return self._gauges[key]

    def histogram(self, name: str, labels: Optional[Dict[str, str]] = None) -> Histogram:
        key = self._key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = Histogram(name=name, labels=labels or {})
        return self._histograms[key]

    def snapshot(self) -> dict:
        """Return a point-in-time snapshot of all metrics."""
        return {
            "counters":   [c.to_dict() for c in self._counters.values()],
            "gauges":     [g.to_dict() for g in self._gauges.values()],
            "histograms": [h.to_dict() for h in self._histograms.values()],
        }

    def reset(self) -> None:
        """Clear all metrics. Used in tests."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()

    @staticmethod
    def _key(name: str, labels: Optional[Dict[str, str]]) -> str:
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
