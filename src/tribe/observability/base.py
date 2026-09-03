from __future__ import annotations

from typing import Any


class Observer:
    """No-op observer. Subclasses render a live view of a run."""

    def run_start(self, session_id: str, user_input: str) -> None: ...

    def compaction(self, summary: Any) -> None: ...

    def model_request(self, estimated_tokens: int, message_count: int) -> None: ...

    def model_response(self, response: Any) -> None: ...

    def approval(self, decision: Any) -> None: ...

    def tool_start(self, name: str, args: dict[str, Any]) -> None: ...

    def tool_end(self, name: str, result: Any, duration: float) -> None: ...

    def run_end(self, result: Any) -> None: ...


class NullObserver(Observer):
    pass
