from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from ..workspace import WorkspaceError
from .base import Tool, ToolContext, ToolResult

_MAX_MATCHES = 200


class GrepTool(Tool):
    name = "grep"
    description = "Search file contents under a path for a regular expression."
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regular expression to search for."},
            "path": {
                "type": "string",
                "description": "File or directory to search (default: workspace root).",
            },
        },
        "required": ["pattern"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        try:
            regex = re.compile(args["pattern"])
        except re.error as exc:
            return ToolResult.fail(f"invalid pattern: {exc}")

        try:
            base = ctx.workspace.resolve(args.get("path", "."))
        except WorkspaceError as exc:
            return ToolResult.fail(str(exc))

        if not base.exists():
            return ToolResult.fail(f"no such file or directory: {args.get('path', '.')}")

        files = [base] if base.is_file() else _walk(base)
        matches: list[str] = []
        for file in files:
            try:
                rel = file.relative_to(ctx.workspace.root)
            except ValueError:
                rel = file
            try:
                with file.open("r", encoding="utf-8", errors="ignore") as fh:
                    for lineno, line in enumerate(fh, 1):
                        if regex.search(line):
                            matches.append(f"{rel}:{lineno}:{line.rstrip()}")
                            if len(matches) >= _MAX_MATCHES:
                                return ToolResult.ok(
                                    "\n".join(matches), truncated=True, count=len(matches)
                                )
            except OSError:
                continue

        if not matches:
            return ToolResult.ok("", count=0)
        return ToolResult.ok("\n".join(matches), count=len(matches))


def _walk(base):
    for root, dirs, names in os.walk(base):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in names:
            yield Path(root) / name
