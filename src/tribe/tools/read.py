from __future__ import annotations

from typing import Any

from ..workspace import WorkspaceError
from .base import Tool, ToolContext, ToolResult


class ReadTool(Tool):
    name = "read"
    description = "Read a file's contents, or list a directory's entries."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to the workspace."},
        },
        "required": ["path"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        try:
            target = ctx.workspace.resolve(args["path"])
        except WorkspaceError as exc:
            return ToolResult.fail(str(exc))

        if not target.exists():
            return ToolResult.fail(f"no such file or directory: {args['path']}")

        if target.is_dir():
            entries = sorted(
                p.name + ("/" if p.is_dir() else "") for p in target.iterdir()
            )
            return ToolResult.ok("\n".join(entries), kind="directory", count=len(entries))

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolResult.fail(str(exc))
        return ToolResult.ok(content, kind="file", bytes=len(content))
