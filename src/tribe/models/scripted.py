from __future__ import annotations

from typing import Any, Callable

from ..sessions.messages import Message
from .base import Model, ModelResponse

Step = ModelResponse | Callable[[list[Message]], ModelResponse]


class ScriptedModel(Model):
    """An offline model that replays a fixed list of responses. For tests and dry runs."""

    def __init__(self, steps: list[Step], name: str = "scripted", context_limit: int = 200_000):
        self.name = name
        self.context_limit = context_limit
        self.steps = list(steps)
        self.calls: list[dict[str, Any]] = []
        self._index = 0

    def complete(self, system, messages, tools=None):
        self.calls.append({"system": system, "messages": list(messages), "tools": tools})
        if self._index >= len(self.steps):
            return ModelResponse(text="")
        step = self.steps[self._index]
        self._index += 1
        return step(messages) if callable(step) else step
