from __future__ import annotations

from typing import Any

from textual.message import Message


class RunStarted(Message):
    def __init__(self, session_id: str, user_input: str) -> None:
        super().__init__()
        self.session_id = session_id
        self.user_input = user_input


class ModelActivity(Message):
    def __init__(self, estimated_tokens: int, message_count: int) -> None:
        super().__init__()
        self.estimated_tokens = estimated_tokens
        self.message_count = message_count


class ToolStarted(Message):
    def __init__(self, name: str, args: dict[str, Any]) -> None:
        super().__init__()
        self.name = name
        self.args = args


class ToolEnded(Message):
    def __init__(self, name: str, is_error: bool, error: str | None, duration: float) -> None:
        super().__init__()
        self.name = name
        self.is_error = is_error
        self.error = error
        self.duration = duration


class ApprovalResolved(Message):
    def __init__(self, tool: str, allowed: bool, reason: str) -> None:
        super().__init__()
        self.tool = tool
        self.allowed = allowed
        self.reason = reason


class Compacted(Message):
    def __init__(self, size: int) -> None:
        super().__init__()
        self.size = size


class RunEnded(Message):
    def __init__(self, status: str, final_text: str | None, rounds: int, completed: bool) -> None:
        super().__init__()
        self.status = status
        self.final_text = final_text
        self.rounds = rounds
        self.completed = completed


class RunFailed(Message):
    def __init__(self, error: str) -> None:
        super().__init__()
        self.error = error
