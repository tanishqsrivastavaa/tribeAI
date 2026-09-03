from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RunLimits:
    max_rounds: int = 50
    tool_timeout: float = 120.0
    max_consecutive_failures: int = 3


class RunStatus:
    COMPLETED = "completed"
    MAX_ROUNDS = "max_rounds"
    MAX_CONSECUTIVE_FAILURES = "max_consecutive_failures"
    CANCELLED = "cancelled"


@dataclass
class RunResult:
    session_id: str
    status: str
    final_text: str | None = None
    rounds: int = 0

    @property
    def completed(self) -> bool:
        return self.status == RunStatus.COMPLETED


class Cancellation:
    def __init__(self) -> None:
        self._flag = False

    @property
    def cancelled(self) -> bool:
        return self._flag

    def cancel(self) -> None:
        self._flag = True
