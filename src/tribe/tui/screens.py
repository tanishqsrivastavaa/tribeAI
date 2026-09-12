from __future__ import annotations

import json
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Collapsible, Input, OptionList, Static
from textual.widgets.option_list import Option

from ..sessions import SessionStore
from ..sessions.messages import Role


def _action_detail(tool: str, args: dict[str, Any]) -> str:
    args = args or {}
    if tool == "bash":
        return f"$ {args.get('command', '')}"
    if tool == "write":
        content = args.get("content", "")
        lines = content.splitlines()
        preview = "\n".join(lines[:15])
        if len(lines) > 15:
            preview += f"\n… ({len(lines) - 15} more lines)"
        return f"write {args.get('path', '')}  ({len(content)} bytes)\n\n{preview}"
    if tool == "read":
        return f"read {args.get('path', '')}"
    if tool == "grep":
        return f"grep {args.get('pattern', '')!r} in {args.get('path') or '.'}"
    return json.dumps(args, indent=2)


class ApprovalModal(ModalScreen[dict]):
    BINDINGS = [
        ("y", "approve", "Approve"),
        ("n", "deny", "Deny"),
        ("a", "always", "Always"),
        ("escape", "deny", "Deny"),
    ]

    def __init__(self, tool: str, args: dict[str, Any]) -> None:
        super().__init__()
        self.tool = tool
        self.args = args or {}

    def compose(self) -> ComposeResult:
        with Vertical(id="approval-box"):
            yield Static(f"Approve [b]{self.tool}[/b]?", id="approval-title")
            yield Static(_action_detail(self.tool, self.args), id="approval-action", markup=False)
            with Collapsible(title="raw arguments", collapsed=True):
                yield Static(json.dumps(self.args, indent=2), markup=False)
            yield Button("Approve (y)", variant="success", id="approve")
            yield Button("Deny (n)", variant="error", id="deny")
            yield Button(f"Always allow {self.tool} (a)", id="always")
            yield Static(
                "y approve · n deny · a always allow · esc cancel", id="approval-keys"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "approve":
            self.action_approve()
        elif event.button.id == "always":
            self.action_always()
        else:
            self.action_deny()

    def action_approve(self) -> None:
        self.dismiss({"allowed": True, "remember": False})

    def action_always(self) -> None:
        self.dismiss({"allowed": True, "remember": True})

    def action_deny(self) -> None:
        self.dismiss({"allowed": False, "remember": False})


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
    """A searchable picker over saved sessions; dismisses with the chosen session id."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("up", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
    ]

    def __init__(self, store: SessionStore, current_id: str) -> None:
        super().__init__()
        self.store = store
        self.current_id = current_id
        self.rows = session_rows(store)

    def compose(self) -> ComposeResult:
        with Vertical(id="login-box"):
            yield Static("Sessions", id="login-title")
            yield Static("type to filter · ↑/↓ to move · enter to open · esc to cancel", id="login-hint")
            yield Input(placeholder="filter…", id="session-filter")
            yield OptionList(id="sessions-list")

    def on_mount(self) -> None:
        self._populate("")
        self.query_one("#session-filter", Input).focus()

    def _populate(self, query: str) -> None:
        query = query.lower()
        option_list = self.query_one(OptionList)
        option_list.clear_options()
        for session_id, count, preview, _ in self.rows:
            text = (preview or "(empty)").replace("\n", " ")
            if query and query not in text.lower() and query not in session_id.lower():
                continue
            marker = "•" if session_id == self.current_id else " "
            option_list.add_option(
                Option(f"{marker} {session_id[:8]}  {count:>3} msgs  {text[:48]}", id=session_id)
            )
        if option_list.option_count:
            option_list.highlighted = 0

    def on_input_changed(self, event: Input.Changed) -> None:
        self._populate(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        option_list = self.query_one(OptionList)
        if option_list.highlighted is not None:
            option = option_list.get_option_at_index(option_list.highlighted)
            self.dismiss(option.id)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(event.option.id)

    def action_cursor_up(self) -> None:
        self.query_one(OptionList).action_cursor_up()

    def action_cursor_down(self) -> None:
        self.query_one(OptionList).action_cursor_down()

    def action_cancel(self) -> None:
        self.dismiss(None)


_HELP_TEXT = """\
Commands
  /login      choose a provider, enter an API key, pick a model
  /model      switch the active model
  /sessions   browse and resume past sessions (searchable)
  /new        start a fresh session
  /clear      clear the transcript view
  /help       show this help

Keys
  Enter         send the message
  Shift+Enter   insert a newline (also Ctrl+J)
  ↑ / ↓         previous / next prompt from history
  Tab           accept the highlighted slash-command
  Ctrl+C        interrupt the current turn (then edit & send to redirect)
  F1            this help
  Ctrl+Q        quit

While the agent works you can keep typing — Enter queues a follow-up,
Ctrl+C interrupts so you can redirect immediately."""


class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        ("escape", "close", "Close"),
        ("q", "close", "Close"),
        ("enter", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="login-box"):
            yield Static("Tribe — help", id="login-title")
            yield Static(_HELP_TEXT, id="help-body", markup=False)
            yield Static("esc or q to close", id="login-hint")

    def action_close(self) -> None:
        self.dismiss(None)
