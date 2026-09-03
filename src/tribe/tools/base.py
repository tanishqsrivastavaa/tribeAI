from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..workspace import Workspace


class ToolValidationError(Exception):
    pass


@dataclass
class ToolResult:
    output: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"

    @property
    def is_error(self) -> bool:
        return self.status == "error"

    @classmethod
    def ok(cls, output: str = "", **metadata: Any) -> ToolResult:
        return cls(output=output, metadata=metadata, status="ok")

    @classmethod
    def fail(cls, error: str, output: str = "", **metadata: Any) -> ToolResult:
        return cls(output=output, error=error, metadata=metadata, status="error")


@dataclass
class ToolContext:
    workspace: Workspace
    timeout: float | None = None


_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def validate_args(args: dict[str, Any], schema: dict[str, Any]) -> None:
    if schema.get("type") != "object":
        return
    if not isinstance(args, dict):
        raise ToolValidationError("arguments must be an object")
    for key in schema.get("required", []):
        if key not in args:
            raise ToolValidationError(f"missing required argument: {key}")
    props = schema.get("properties", {})
    for key, value in args.items():
        spec = props.get(key)
        if not spec or "type" not in spec:
            continue
        expected = _TYPES.get(spec["type"])
        if expected and not isinstance(value, expected):
            raise ToolValidationError(f"argument '{key}' must be {spec['type']}")


class Tool(ABC):
    name: str
    description: str
    input_schema: dict[str, Any]

    def spec(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        validate_args(args, self.input_schema)
        return self.run(args, ctx)

    @abstractmethod
    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult: ...
