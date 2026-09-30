"""JARVIS OS - Tool Execution Framework"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ToolCategory(str, Enum):
    SYSTEM = "system"
    FILE = "file"
    BROWSER = "browser"
    TERMINAL = "terminal"
    COMMUNICATION = "communication"
    AUTOMATION = "automation"
    SCIENTIFIC = "scientific"


@dataclass
class ToolResult:
    success: bool
    output: Any
    error: Optional[str] = None
    requires_confirmation: bool = False


class BaseTool(ABC):
    def __init__(self, name: str, description: str, category: ToolCategory,
                 requires_confirmation: bool = False):
        self.name = name
        self.description = description
        self.category = category
        self.requires_confirmation = requires_confirmation

    @abstractmethod
    async def execute(self, **params) -> ToolResult:
        pass

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "requires_confirmation": self.requires_confirmation
        }


class FileReadTool(BaseTool):
    def __init__(self):
        super().__init__("read_file", "Read file contents", ToolCategory.FILE)

    async def execute(self, path: str, **params) -> ToolResult:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return ToolResult(success=True, output=f.read())
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class FileWriteTool(BaseTool):
    def __init__(self):
        super().__init__("write_file", "Write content to file",
                         ToolCategory.FILE, requires_confirmation=True)

    async def execute(self, path: str, content: str, **params) -> ToolResult:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return ToolResult(success=True, output=f"Written to {path}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class ShellTool(BaseTool):
    def __init__(self):
        super().__init__("run_command", "Execute shell command",
                         ToolCategory.TERMINAL, requires_confirmation=True)

    async def execute(self, command: str, **params) -> ToolResult:
        import asyncio
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return ToolResult(
                success=proc.returncode == 0,
                output=stdout.decode(),
                error=stderr.decode() if stderr else None
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class KiroAssistTool(BaseTool):
    """Wraps kiro_tool.ask_kiro() as a registered BaseTool."""

    def __init__(self):
        super().__init__(
            name="kiro_assist",
            description="Ask Kiro CLI for coding help, architecture reasoning, and deep analysis",
            category=ToolCategory.AUTOMATION,
        )

    async def execute(self, query: str = "", **params) -> ToolResult:
        try:
            from app.tools.kiro_tool import ask_kiro
            result = await ask_kiro(query)
            if result["success"]:
                return ToolResult(success=True, output=result["response"])
            return ToolResult(success=False, output=None, error=result["error"])
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class ToolRegistry:
    """Central registry for all available tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._register_defaults()

    def _register_defaults(self):
        from app.tools.web_search import WebSearchTool
        from app.tools.live_data import WeatherTool, GoldPriceTool, LocationTool
        from app.tools.code_generator import CodeGeneratorTool, ProjectScaffoldTool, ListWorkspaceTool
        self.register(FileReadTool())
        self.register(FileWriteTool())
        self.register(ShellTool())
        self.register(WebSearchTool())
        self.register(WeatherTool())
        self.register(GoldPriceTool())
        self.register(LocationTool())
        self.register(CodeGeneratorTool())
        self.register(ProjectScaffoldTool())
        self.register(ListWorkspaceTool())
        self.register(KiroAssistTool())

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    async def execute(self, name: str, confirmed: bool = False, **params) -> ToolResult:
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, output=None, error=f"Tool '{name}' not found")
        if tool.requires_confirmation and not confirmed:
            return ToolResult(
                success=False, output=None,
                error="Action requires user confirmation",
                requires_confirmation=True
            )
        return await tool.execute(**params)

    def list_tools(self) -> List[dict]:
        return [t.schema() for t in self._tools.values()]
