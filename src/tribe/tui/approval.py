from __future__ import annotations

import threading
from typing import Any

from . import messages as m
from .screens import ApprovalModal


class TuiApprover:
    """Blocks the worker thread on an approval modal; remembers per-session choices."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self._session_allow: set[str] = set()

    def __call__(self, tool: str, args: dict[str, Any]) -> bool:
        if tool in self._session_allow:
            return True

        self.app.post_message(m.ApprovalRequested(tool, args))
        done = threading.Event()
        result: dict[str, bool] = {"value": False}

        def show() -> None:
            def resolved(value: Any) -> None:
                if isinstance(value, dict):
                    allowed = bool(value.get("allowed"))
                    if allowed and value.get("remember"):
                        self._session_allow.add(tool)
                else:
                    allowed = bool(value)
                result["value"] = allowed
                done.set()

            self.app.push_screen(ApprovalModal(tool, args), resolved)

        self.app.call_from_thread(show)
        done.wait()
        return result["value"]
