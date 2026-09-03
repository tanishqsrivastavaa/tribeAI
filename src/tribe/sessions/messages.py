from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    SYSTEM = "system"
    SUMMARY = "summary"


class ToolStatus(str, Enum):
    OK = "ok"
    ERROR = "error"


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class Message:
    role: Role
    content: str = ""
    id: str = field(default_factory=_new_id)
    timestamp: float = field(default_factory=time.time)

    tool_name: str | None = None
    call_id: str | None = None
    arguments: dict[str, Any] | None = None
    result: str | None = None
    status: ToolStatus | None = None
    error: str | None = None

    summary_start: str | None = None
    summary_end: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["role"] = self.role.value
        if self.status is not None:
            data["status"] = self.status.value
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        data = dict(data)
        data["role"] = Role(data["role"])
        if data.get("status") is not None:
            data["status"] = ToolStatus(data["status"])
        return cls(**data)


def user(content: str) -> Message:
    return Message(role=Role.USER, content=content)


def assistant(content: str) -> Message:
    return Message(role=Role.ASSISTANT, content=content)


def system(content: str) -> Message:
    return Message(role=Role.SYSTEM, content=content)


def tool_call(
    tool_name: str, call_id: str, arguments: dict[str, Any], content: str = ""
) -> Message:
    return Message(
        role=Role.TOOL_CALL,
        content=content,
        tool_name=tool_name,
        call_id=call_id,
        arguments=arguments,
    )


def tool_result(
    tool_name: str,
    call_id: str,
    result: str,
    status: ToolStatus = ToolStatus.OK,
    error: str | None = None,
) -> Message:
    return Message(
        role=Role.TOOL_RESULT,
        content=result,
        tool_name=tool_name,
        call_id=call_id,
        result=result,
        status=status,
        error=error,
    )


def summary(content: str, start_id: str, end_id: str) -> Message:
    return Message(
        role=Role.SUMMARY,
        content=content,
        summary_start=start_id,
        summary_end=end_id,
    )
