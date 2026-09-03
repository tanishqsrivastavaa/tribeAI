from __future__ import annotations

from ..sessions.messages import Message, Role
from .estimate import estimate_messages, estimate_tokens


class ContextBuilder:
    def __init__(self, instructions: str = "", keep_recent: int = 16, threshold: float = 0.6):
        self.instructions = instructions
        self.keep_recent = keep_recent
        self.threshold = threshold

    def effective_history(self, messages: list[Message]) -> list[Message]:
        last_summary = None
        for m in messages:
            if m.role == Role.SUMMARY:
                last_summary = m

        if last_summary is None:
            return [m for m in messages if m.role != Role.SYSTEM]

        idx = next(
            (i for i, m in enumerate(messages) if m.id == last_summary.summary_end), None
        )
        if idx is None:
            idx = messages.index(last_summary)
        recent = [
            m
            for m in messages[idx + 1 :]
            if m.role not in (Role.SUMMARY, Role.SYSTEM)
        ]
        return [last_summary] + recent

    def budget(self, context_limit: int) -> int:
        return int(context_limit * self.threshold)

    def estimate(self, history: list[Message]) -> int:
        return estimate_tokens(self.instructions) + estimate_messages(history)

    def should_compact(self, messages: list[Message], context_limit: int) -> bool:
        history = self.effective_history(messages)
        if len(history) <= self.keep_recent:
            return False
        return self.estimate(history) >= self.budget(context_limit)

    def build(self, messages: list[Message]) -> tuple[str, list[Message]]:
        return self.instructions, self.effective_history(messages)
