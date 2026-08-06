"""Frino OS - Code Generation Tool
Creates files, scripts, project structures like Kiro/Amazon Q.
"""
from __future__ import annotations
import os
from typing import Dict, List, Optional

from app.tools.registry import BaseTool, ToolCategory, ToolResult

# Base workspace path
WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "workspace"))


class CodeGeneratorTool(BaseTool):
    """Generates and saves code files to workspace."""

    def __init__(self):
        super().__init__(
            "generate_code",
            "Generate and save code/config files (Python, YAML, JS, etc.)",
            ToolCategory.FILE
        )

    async def execute(self, filename: str, content: str, subfolder: str = "", **params) -> ToolResult:
        try:
            if subfolder:
                target_dir = os.path.join(WORKSPACE, subfolder)
            else:
                target_dir = WORKSPACE

            os.makedirs(target_dir, exist_ok=True)
            filepath = os.path.join(target_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            return ToolResult(
                success=True,
                output={"filepath": filepath, "filename": filename, "size": len(content)}
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class ProjectScaffoldTool(BaseTool):
    """Creates entire project structures with multiple files."""

    def __init__(self):
        super().__init__(
            "create_project",
            "Create a project structure with multiple files and folders",
            ToolCategory.FILE
        )

    async def execute(self, project_name: str, files: List[Dict[str, str]], **params) -> ToolResult:
        """
        files: [{"path": "relative/path/file.py", "content": "..."}]
        """
        try:
            project_dir = os.path.join(WORKSPACE, project_name)
            os.makedirs(project_dir, exist_ok=True)
            created = []

            for f in files:
                filepath = os.path.join(project_dir, f["path"])
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, 'w', encoding='utf-8') as fh:
                    fh.write(f["content"])
                created.append(f["path"])

            return ToolResult(
                success=True,
                output={"project_dir": project_dir, "files_created": created}
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class ListWorkspaceTool(BaseTool):
    """Lists files in the workspace."""

    def __init__(self):
        super().__init__(
            "list_workspace",
            "List files and folders in the workspace",
            ToolCategory.FILE
        )

    async def execute(self, path: str = "", **params) -> ToolResult:
        try:
            target = os.path.join(WORKSPACE, path) if path else WORKSPACE
            if not os.path.exists(target):
                return ToolResult(success=True, output={"files": [], "message": "Workspace is empty"})

            items = []
            for root, dirs, files in os.walk(target):
                rel = os.path.relpath(root, WORKSPACE)
                for f in files:
                    items.append(os.path.join(rel, f) if rel != "." else f)

            return ToolResult(success=True, output={"files": items, "count": len(items)})
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
