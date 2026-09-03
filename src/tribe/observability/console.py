from __future__ import annotations

import json
import sys
from typing import Any

from .base import Observer

_ARG_KEYS = ("path", "command", "pattern")


def _short(args: dict[str, Any], limit: int = 80) -> str:
    for key in _ARG_KEYS:
        if key in args:
            return f"{key}={args[key]!r}"[:limit]
    text = json.dumps(args)
    return text if len(text) <= limit else text[:limit] + "…"


class ConsoleObserver(Observer):
    def __init__(self, verbose: bool = False, stream: Any = None):
        self.verbose = verbose
        self.stream = stream or sys.stderr

    def _emit(self, line: str) -> None:
        print(line, file=self.stream, flush=True)

    def run_start(self, session_id: str, user_input: str) -> None:
        if self.verbose:
            self._emit(f"▶ session {session_id}")

    def compaction(self, summary: Any) -> None:
        self._emit(f"↯ compacted history ({len(summary.content)} chars)")

    def model_request(self, estimated_tokens: int, message_count: int) -> None:
        if self.verbose:
            self._emit(f"→ model (~{estimated_tokens} tok, {message_count} msgs)")

    def model_response(self, response: Any) -> None:
        if self.verbose:
            self._emit(
                f"← model (stop={response.stop_reason}, "
                f"tools={len(response.tool_calls)}, "
                f"out={response.usage.output_tokens} tok)"
            )

    def approval(self, decision: Any) -> None:
        if not decision.allowed:
            self._emit(f"⛔ {decision.tool} denied: {decision.reason}")
        elif self.verbose:
            mode = getattr(decision.mode, "value", decision.mode)
            self._emit(f"✓ {decision.tool} {mode}")

    def tool_start(self, name: str, args: dict[str, Any]) -> None:
        self._emit(f"⚙ {name} {_short(args)}")

    def tool_end(self, name: str, result: Any, duration: float) -> None:
        if result.is_error:
            self._emit(f"  ↳ error: {result.error}")
        elif self.verbose:
            self._emit(f"  ↳ ok ({duration * 1000:.0f} ms)")

    def run_end(self, result: Any) -> None:
        if not result.completed:
            self._emit(f"■ stopped: {result.status} after {result.rounds} rounds")
        elif self.verbose:
            self._emit(f"■ done in {result.rounds} rounds")
