# Plugin SDK Documentation

## Overview

The JARVIS OS plugin system allows extending functionality without modifying core code.

## Creating a Plugin

### Directory Structure
```
plugins/
└── your_plugin/
    ├── manifest.json    # Plugin metadata
    └── main.py          # Entry point (must export `Plugin` class)
```

### Manifest Schema
```json
{
  "name": "string (required)",
  "version": "semver string (required)",
  "description": "string (required)",
  "author": "string (required)",
  "entry_point": "string (required) - relative path to main module",
  "capabilities": ["list of action names this plugin handles"]
}
```

### Plugin Class API

```python
from app.plugins.manager import PluginBase

class Plugin(PluginBase):
    def initialize(self, context: dict) -> bool:
        """Called once when plugin is loaded. Return True if successful."""
        pass

    async def execute(self, action: str, params: dict) -> Any:
        """Handle an action request."""
        pass

    def get_actions(self) -> list[str]:
        """Return list of actions this plugin can handle."""
        pass

    def shutdown(self):
        """Cleanup when plugin is unloaded."""
        pass
```

### Context Object
The `context` dict passed to `initialize` contains:
- `memory`: Reference to MemoryManager
- `tools`: Reference to ToolRegistry
- `config`: Application settings

## Lifecycle
1. Discovery: PluginManager scans `plugins/` for directories with `manifest.json`
2. Loading: `importlib` loads the module, instantiates `Plugin`
3. Initialization: `initialize(context)` is called
4. Execution: `execute(action, params)` called on demand
5. Shutdown: `shutdown()` called on unload or app exit

## Example: Weather Plugin
```python
import httpx
from app.plugins.manager import PluginBase

class Plugin(PluginBase):
    def initialize(self, context):
        self.api_key = context.get("weather_api_key", "")
        return bool(self.api_key)

    async def execute(self, action, params):
        if action == "get_weather":
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://api.weather.example/v1/current",
                    params={"q": params["city"], "key": self.api_key}
                )
                return resp.json()
        return {"error": "Unknown action"}

    def get_actions(self):
        return ["get_weather"]

    def shutdown(self):
        pass
```
