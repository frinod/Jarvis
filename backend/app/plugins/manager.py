"""JARVIS OS - Plugin Architecture"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import importlib
import os


@dataclass
class PluginManifest:
    name: str
    version: str
    description: str
    author: str
    entry_point: str
    capabilities: List[str]


class PluginBase(ABC):
    @abstractmethod
    def initialize(self, context: dict) -> bool:
        pass

    @abstractmethod
    async def execute(self, action: str, params: dict) -> Any:
        pass

    @abstractmethod
    def get_actions(self) -> List[str]:
        pass

    @abstractmethod
    def shutdown(self):
        pass


class PluginManager:
    """Discovers, loads, and manages plugins."""

    def __init__(self, plugin_dir: str = "plugins"):
        self.plugin_dir = plugin_dir
        self._plugins: Dict[str, PluginBase] = {}

    def discover(self) -> List[str]:
        """Find available plugins in the plugin directory."""
        found = []
        if not os.path.exists(self.plugin_dir):
            return found
        for item in os.listdir(self.plugin_dir):
            manifest_path = os.path.join(self.plugin_dir, item, "manifest.json")
            if os.path.isfile(manifest_path):
                found.append(item)
        return found

    def load(self, name: str, context: dict = None) -> bool:
        """Load and initialize a plugin by name."""
        try:
            module = importlib.import_module(f"plugins.{name}.main")
            plugin: PluginBase = module.Plugin()
            if plugin.initialize(context or {}):
                self._plugins[name] = plugin
                return True
        except Exception:
            pass
        return False

    async def execute_plugin(self, name: str, action: str, params: dict) -> Any:
        plugin = self._plugins.get(name)
        if not plugin:
            return {"error": f"Plugin '{name}' not loaded"}
        return await plugin.execute(action, params)

    def list_loaded(self) -> List[str]:
        return list(self._plugins.keys())

    def unload(self, name: str):
        plugin = self._plugins.pop(name, None)
        if plugin:
            plugin.shutdown()
