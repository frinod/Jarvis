"""
core/plugins/loader.py
======================
Plugin Loader for the JARVIS Kernel.

Loads provider implementations dynamically from dotted import paths
(the `plugin_class` fields in BrokerProfile, LLMProfile, etc.).

Responsibilities
----------------
  Import resolution  -- "app.brokers.angel_one.AngelOneProvider" -> class
  Validation         -- loaded class must implement the expected interface
  Caching            -- each dotted path imported once per process
  Error isolation    -- import failures produce clear, actionable errors
  Registry wiring    -- loaded classes registered in ServiceRegistry

Design principles
-----------------
  Fail-fast on bad plugin_class -- clear error at load time, not at call time
  Interface validation -- issubclass check before accepting a plugin
  Import cache -- importlib called once per dotted path
  No magic -- explicit plugin_class field, no auto-discovery

500-module test
---------------
  "Will this package still make sense when JARVIS has 500+ modules?"
  Yes. Every provider in the system is loaded here. The loader is
  the kernel's dynamic linker. It never grows beyond this single
  responsibility.
"""
from __future__ import annotations

import importlib
from typing import Any, Dict, Optional, Type


class PluginLoadError(Exception):
    """Raised when a plugin cannot be loaded or fails interface validation."""
    pass


class PluginLoader:
    """
    Dynamic class loader for JARVIS Kernel plugins.

    Usage
    -----
        loader = PluginLoader()

        # Load a class from a dotted path
        cls = loader.load("app.brokers.angel_one.AngelOneProvider")

        # Load and validate against an interface
        cls = loader.load(
            "app.brokers.angel_one.AngelOneProvider",
            expected_base=BrokerProvider
        )

        # Instantiate directly
        instance = loader.instantiate(
            "app.core.llm.GeminiProvider",
            expected_base=LLMProvider,
            api_key="...", model="gemini-2.0-flash"
        )
    """

    def __init__(self) -> None:
        self._cache: Dict[str, type] = {}

    def load(
        self,
        dotted_path:   str,
        expected_base: Optional[Type] = None,
    ) -> type:
        """
        Import and return the class at `dotted_path`.

        dotted_path:   e.g. "app.brokers.angel_one.AngelOneProvider"
        expected_base: if provided, the loaded class must be a subclass

        Raises PluginLoadError on any failure.
        """
        if not dotted_path or not dotted_path.strip():
            raise PluginLoadError("plugin_class must not be empty")

        if dotted_path in self._cache:
            cls = self._cache[dotted_path]
        else:
            cls = self._import(dotted_path)
            self._cache[dotted_path] = cls

        if expected_base is not None:
            if not (isinstance(cls, type) and issubclass(cls, expected_base)):
                raise PluginLoadError(
                    f"{dotted_path!r} does not implement {expected_base.__name__}"
                )

        return cls

    def instantiate(
        self,
        dotted_path:   str,
        expected_base: Optional[Type] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Load the class at `dotted_path` and instantiate it with *args/**kwargs.
        """
        cls = self.load(dotted_path, expected_base)
        try:
            return cls(*args, **kwargs)
        except Exception as exc:
            raise PluginLoadError(
                f"Failed to instantiate {dotted_path!r}: {exc}"
            ) from exc

    def is_loadable(self, dotted_path: str) -> bool:
        """
        Return True if the dotted path can be imported without error.
        Does not validate against an interface.
        """
        try:
            self.load(dotted_path)
            return True
        except PluginLoadError:
            return False

    def clear_cache(self) -> None:
        """Clear the import cache. Useful in tests."""
        self._cache.clear()

    def cached_paths(self) -> list:
        """Return list of dotted paths currently in the import cache."""
        return list(self._cache.keys())

    # ── Internal ──────────────────────────────────────────────

    def _import(self, dotted_path: str) -> type:
        """Split dotted_path into module + attribute and import."""
        parts = dotted_path.rsplit(".", 1)
        if len(parts) != 2:
            raise PluginLoadError(
                f"Invalid plugin_class {dotted_path!r}: "
                f"must be 'module.ClassName'"
            )
        module_path, class_name = parts

        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise PluginLoadError(
                f"Cannot import module {module_path!r} "
                f"for plugin {dotted_path!r}: {exc}"
            ) from exc

        cls = getattr(module, class_name, None)
        if cls is None:
            raise PluginLoadError(
                f"Module {module_path!r} has no attribute {class_name!r}"
            )

        if not isinstance(cls, type):
            raise PluginLoadError(
                f"{dotted_path!r} is not a class (got {type(cls).__name__})"
            )

        return cls
