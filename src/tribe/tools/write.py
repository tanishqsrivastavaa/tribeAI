from __future__ import annotations

from typing import Any

from ..workspace import WorkspaceError
from .base import Tool, ToolContext, ToolResult


class WriteTool(Tool):
    name = "write"
    description = "Create or overwrite a file with the given content."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to the workspace."},
            "content": {"type": "string", "description": "Full file contents to write."},
        },
        "required": ["path", "content"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        try:
            target = ctx.workspace.resolve(args["path"])
        except WorkspaceError as exc:
            return ToolResult.fail(str(exc))

        if target.is_dir():
            return ToolResult.fail(f"path is a directory: {args['path']}")

        content = args["content"]
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return ToolResult.fail(str(exc))
        return ToolResult.ok(f"wrote {len(content)} bytes to {args['path']}", bytes=len(content))
