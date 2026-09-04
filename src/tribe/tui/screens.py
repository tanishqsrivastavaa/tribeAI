from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from ..observability.console import _short


class ApprovalModal(ModalScreen[bool]):
    BINDINGS = [
        ("y", "approve", "Approve"),
        ("n", "deny", "Deny"),
        ("escape", "deny", "Deny"),
    ]

    def __init__(self, tool: str, args: dict[str, Any]) -> None:
        super().__init__()
        self.tool = tool
        self.args = args

    def compose(self) -> ComposeResult:
        with Vertical(id="approval-box"):
            yield Static(f"Approve [b]{self.tool}[/b]?", id="approval-title")
            yield Static(_short(self.args, limit=200), id="approval-args")
            yield Button("Approve (y)", variant="success", id="approve")
            yield Button("Deny (n)", variant="error", id="deny")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "approve")

    def action_approve(self) -> None:
        self.dismiss(True)

    def action_deny(self) -> None:
        self.dismiss(False)
