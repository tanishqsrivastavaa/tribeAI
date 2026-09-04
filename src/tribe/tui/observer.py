from __future__ import annotations

from typing import Any

from ..observability import Observer
from . import messages as m


class TuiObserver(Observer):
    """Translates agent run events into thread-safe messages posted to the app."""

    def __init__(self, app: Any) -> None:
        self.app = app

    def run_start(self, session_id: str, user_input: str) -> None:
        self.app.post_message(m.RunStarted(session_id, user_input))

    def compaction(self, summary: Any) -> None:
        self.app.post_message(m.Compacted(len(summary.content)))

    def model_request(self, estimated_tokens: int, message_count: int) -> None:
        self.app.post_message(m.ModelActivity(estimated_tokens, message_count))

    def tool_start(self, name: str, args: dict[str, Any]) -> None:
        self.app.post_message(m.ToolStarted(name, args))

    def tool_end(self, name: str, result: Any, duration: float) -> None:
        self.app.post_message(
            m.ToolEnded(name, result.is_error, result.error, duration)
        )

    def approval(self, decision: Any) -> None:
        self.app.post_message(
            m.ApprovalResolved(decision.tool, decision.allowed, decision.reason)
        )

    def run_end(self, result: Any) -> None:
        self.app.post_message(
            m.RunEnded(result.status, result.final_text, result.rounds, result.completed)
        )
