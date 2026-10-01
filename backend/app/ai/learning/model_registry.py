"""
app/ai/learning/model_registry.py
===================================
ModelRegistry -- versioned in-memory model store with rollback support.

Design
------
  - Stores model objects (any type) keyed by version string.
  - Maintains an ordered version history for rollback.
  - active_version tracks the currently deployed model.
  - rollback() reverts to the previous version.
  - In-memory for Phase 7D. Phase 8 can add disk/S3 persistence
    without changing the interface.

  The registry is strictly advisory — it stores and retrieves model
  objects but never calls them. The Brain or ForecastingEngine decides
  when to use a registered model.

Resilience (Rule 11b):
  All methods return None / False on failure. Never raise.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── ModelRecord ───────────────────────────────────────────────────────────────

@dataclass
class ModelRecord:
    """Metadata for one registered model version."""
    version:      str
    model:        Any
    registered_at: float = field(default_factory=time.time)
    description:  str    = ""
    metrics:      Dict[str, float] = field(default_factory=dict)
    metadata:     Dict[str, Any]   = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "version":       self.version,
            "registered_at": self.registered_at,
            "description":   self.description,
            "metrics":       self.metrics,
        }


# ── ModelRegistry ─────────────────────────────────────────────────────────────

class ModelRegistry:
    """
    In-memory versioned model store.

    Usage
    -----
        registry = ModelRegistry()
        registry.register("v1.0", model=xgb_model, description="initial")
        registry.register("v1.1", model=xgb_v2,    description="retrained")
        registry.set_active("v1.1")

        model = registry.get_active()
        registry.rollback()          # reverts to v1.0
    """

    def __init__(self) -> None:
        self._models:  Dict[str, ModelRecord] = {}
        self._history: List[str]              = []   # ordered by registration time
        self._active:  Optional[str]          = None

    # ── Write ─────────────────────────────────────────────────────────

    def register(
        self,
        version:     str,
        model:       Any,
        description: str                    = "",
        metrics:     Optional[Dict[str, float]] = None,
        metadata:    Optional[Dict[str, Any]]   = None,
    ) -> bool:
        """
        Register a model version. Returns True on success.
        If version already exists, it is overwritten.
        Never raises.
        """
        try:
            record = ModelRecord(
                version=     version,
                model=       model,
                description= description,
                metrics=     metrics or {},
                metadata=    metadata or {},
            )
            self._models[version] = record
            if version not in self._history:
                self._history.append(version)
            # Auto-activate first registered model
            if self._active is None:
                self._active = version
            return True
        except Exception as exc:
            logger.debug("ModelRegistry.register failed: %s", exc)
            return False

    def set_active(self, version: str) -> bool:
        """
        Set the active model version. Returns True if version exists.
        Never raises.
        """
        try:
            if version not in self._models:
                logger.debug("ModelRegistry.set_active: version %s not found", version)
                return False
            self._active = version
            return True
        except Exception as exc:
            logger.debug("ModelRegistry.set_active failed: %s", exc)
            return False

    def rollback(self) -> Optional[str]:
        """
        Revert to the previous version in history.
        Returns the version rolled back to, or None if no previous version.
        Never raises.
        """
        try:
            if self._active is None or len(self._history) < 2:
                return None
            current_idx = self._history.index(self._active)
            if current_idx == 0:
                return None   # already at oldest
            prev_version = self._history[current_idx - 1]
            self._active = prev_version
            return prev_version
        except Exception as exc:
            logger.debug("ModelRegistry.rollback failed: %s", exc)
            return None

    def unregister(self, version: str) -> bool:
        """Remove a version. Returns True if it existed. Never raises."""
        try:
            if version not in self._models:
                return False
            del self._models[version]
            self._history = [v for v in self._history if v != version]
            if self._active == version:
                self._active = self._history[-1] if self._history else None
            return True
        except Exception as exc:
            logger.debug("ModelRegistry.unregister failed: %s", exc)
            return False

    # ── Read ──────────────────────────────────────────────────────────

    def get(self, version: str) -> Optional[Any]:
        """Return the model object for a version, or None."""
        record = self._models.get(version)
        return record.model if record else None

    def get_record(self, version: str) -> Optional[ModelRecord]:
        """Return the full ModelRecord for a version, or None."""
        return self._models.get(version)

    def get_active(self) -> Optional[Any]:
        """Return the currently active model object, or None."""
        if self._active is None:
            return None
        return self.get(self._active)

    def get_active_version(self) -> Optional[str]:
        """Return the active version string, or None."""
        return self._active

    def list_versions(self) -> List[str]:
        """Return all registered versions in registration order."""
        return list(self._history)

    # ── Introspection ─────────────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self._models)

    def stats(self) -> dict:
        return {
            "size":           self.size,
            "active_version": self._active,
            "versions":       self.list_versions(),
        }
