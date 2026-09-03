from __future__ import annotations

import subprocess
from typing import Any

from .base import Tool, ToolContext, ToolResult


class BashTool(Tool):
    name = "bash"
    description = "Run a shell command with the workspace as the working directory."
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute."},
        },
        "required": ["command"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        try:
            completed = subprocess.run(
                args["command"],
                shell=True,
                cwd=ctx.workspace.root,
                capture_output=True,
                text=True,
                timeout=ctx.timeout,
            )
        except subprocess.TimeoutExpired:
            return ToolResult.fail(
                f"command timed out after {ctx.timeout}s", exit_code=None
            )

        output = completed.stdout
        if completed.stderr:
            output += ("\n" if output else "") + completed.stderr

        if completed.returncode != 0:
            return ToolResult.fail(
                f"exited with code {completed.returncode}",
                output=output,
                exit_code=completed.returncode,
            )
        return ToolResult.ok(output, exit_code=0)
