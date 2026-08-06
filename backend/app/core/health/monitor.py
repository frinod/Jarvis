"""
core/health/monitor.py
======================
Health Monitor for the JARVIS Kernel.

Runs registered health checks and aggregates results into a
system-wide health status. Populates ServiceRegistry status slots.

Design principles
-----------------
  Check-based -- each component registers an async health check
  Aggregated status -- HEALTHY only if all required checks pass
  Non-blocking -- checks run concurrently with timeout
  Observable -- last result per check, overall system status
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional


class HealthStatus(str, Enum):
    HEALTHY   = "healthy"
    DEGRADED  = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN   = "unknown"


@dataclass
class HealthCheckResult:
    name:       str
    status:     HealthStatus
    message:    str       = ""
    duration_s: float     = 0.0
    checked_at: float     = 0.0    # monotonic timestamp

    def to_dict(self) -> dict:
        return {
            "name":       self.name,
            "status":     self.status,
            "message":    self.message,
            "duration_s": round(self.duration_s, 4),
        }


@dataclass
class HealthCheck:
    name:      str
    fn:        Callable
    required:  bool  = True     # if False, failure -> DEGRADED not UNHEALTHY
    timeout_s: float = 5.0
    last_result: Optional[HealthCheckResult] = None


class HealthMonitor:
    """
    System health monitor for the JARVIS Kernel.

    Usage
    -----
        monitor = HealthMonitor()

        @monitor.check("database", required=True)
        async def check_db() -> HealthStatus:
            await db.ping()
            return HealthStatus.HEALTHY

        result = await monitor.run_all()
        print(result.overall)
    """

    def __init__(self) -> None:
        self._checks: Dict[str, HealthCheck] = {}

    def check(self, name: str, required: bool = True, timeout_s: float = 5.0) -> Callable:
        """Decorator to register a health check function."""
        def decorator(fn: Callable) -> Callable:
            self.register(name, fn, required, timeout_s)
            return fn
        return decorator

    def register(
        self,
        name:      str,
        fn:        Callable,
        required:  bool  = True,
        timeout_s: float = 5.0,
    ) -> "HealthMonitor":
        self._checks[name] = HealthCheck(
            name=name, fn=fn, required=required, timeout_s=timeout_s
        )
        return self

    async def run_all(self) -> "SystemHealth":
        """Run all checks concurrently and return aggregated SystemHealth."""
        tasks = [self._run_check(c) for c in self._checks.values()]
        results = await asyncio.gather(*tasks)
        return SystemHealth(results=list(results))

    async def run_one(self, name: str) -> Optional[HealthCheckResult]:
        """Run a single check by name."""
        check = self._checks.get(name)
        if check is None:
            return None
        return await self._run_check(check)

    def last_result(self, name: str) -> Optional[HealthCheckResult]:
        check = self._checks.get(name)
        return check.last_result if check else None

    def check_names(self) -> List[str]:
        return list(self._checks.keys())

    async def _run_check(self, check: HealthCheck) -> HealthCheckResult:
        start = time.monotonic()
        try:
            coro = check.fn()
            if asyncio.iscoroutine(coro):
                status = await asyncio.wait_for(coro, timeout=check.timeout_s)
            else:
                status = coro
            if not isinstance(status, HealthStatus):
                status = HealthStatus.HEALTHY
            duration = time.monotonic() - start
            result = HealthCheckResult(
                name=check.name, status=status,
                duration_s=duration, checked_at=start
            )
        except asyncio.TimeoutError:
            duration = time.monotonic() - start
            result = HealthCheckResult(
                name=check.name, status=HealthStatus.UNHEALTHY,
                message=f"Timed out after {check.timeout_s}s",
                duration_s=duration, checked_at=start
            )
        except Exception as exc:
            duration = time.monotonic() - start
            result = HealthCheckResult(
                name=check.name, status=HealthStatus.UNHEALTHY,
                message=str(exc), duration_s=duration, checked_at=start
            )
        check.last_result = result
        return result


@dataclass
class SystemHealth:
    """Aggregated health status from all checks."""
    results: List[HealthCheckResult]

    @property
    def overall(self) -> HealthStatus:
        if not self.results:
            return HealthStatus.UNKNOWN
        statuses = {r.status for r in self.results}
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    @property
    def is_healthy(self) -> bool:
        return self.overall == HealthStatus.HEALTHY

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "checks":  [r.to_dict() for r in self.results],
        }
