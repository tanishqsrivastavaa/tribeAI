from __future__ import annotations

from .bash import BashTool
from .base import Tool, ToolContext, ToolResult, ToolValidationError, validate_args
from .grep import GrepTool
from .read import ReadTool
from .write import WriteTool


def default_tools() -> list[Tool]:
    return [ReadTool(), GrepTool(), WriteTool(), BashTool()]


def registry(tools: list[Tool] | None = None) -> dict[str, Tool]:
    return {tool.name: tool for tool in (tools or default_tools())}


def specs(tools: list[Tool] | None = None) -> list[dict]:
    return [tool.spec() for tool in (tools or default_tools())]


__all__ = [
    "Tool",
    "ToolContext",
    "ToolResult",
    "ToolValidationError",
    "validate_args",
    "ReadTool",
    "GrepTool",
    "WriteTool",
    "BashTool",
    "default_tools",
    "registry",
    "specs",
]
