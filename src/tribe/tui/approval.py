from __future__ import annotations

import threading
from typing import Any

from .screens import ApprovalModal


class TuiApprover:
    """An approval asker that blocks the worker thread until a modal is resolved."""

    def __init__(self, app: Any) -> None:
        self.app = app

    def __call__(self, tool: str, args: dict[str, Any]) -> bool:
        done = threading.Event()
        result: dict[str, bool] = {"value": False}

        def show() -> None:
            def resolved(value: bool | None) -> None:
                result["value"] = bool(value)
                done.set()

            self.app.push_screen(ApprovalModal(tool, args), resolved)

        self.app.call_from_thread(show)
        done.wait()
        return result["value"]
