from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from ..observability.console import _short
from ..sessions import SessionStore
from ..sessions.messages import Role


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


def session_rows(store: SessionStore) -> list[tuple[str, int, str, float]]:
    """(session_id, message_count, first-user-message preview, last timestamp)."""
    rows = []
    for session_id in store.list_sessions():
        try:
            history = store.load(session_id)
        except FileNotFoundError:
            continue
        last_ts = history[-1].timestamp if history else 0.0
        preview = next(
            (msg.content for msg in history if msg.role == Role.USER and msg.content), ""
        )
        rows.append((session_id, len(history), preview, last_ts))
    rows.sort(key=lambda row: row[3], reverse=True)
    return rows


class SessionsScreen(ModalScreen[str | None]):
    """A picker over saved sessions; dismisses with the chosen session id."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, store: SessionStore, current_id: str) -> None:
        super().__init__()
        self.store = store
        self.current_id = current_id

    def compose(self) -> ComposeResult:
        with Vertical(id="login-box"):
            yield Static("Sessions", id="login-title")
            yield Static("↑/↓ to move, enter to open, esc to cancel", id="login-hint")
            options = []
            for session_id, count, preview, _ in session_rows(self.store):
                marker = "•" if session_id == self.current_id else " "
                text = (preview[:40] or "(empty)").replace("\n", " ")
                options.append(
                    Option(f"{marker} {session_id[:8]}  {count:>3} msgs  {text}", id=session_id)
                )
            yield OptionList(*options, id="sessions-list")

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)
