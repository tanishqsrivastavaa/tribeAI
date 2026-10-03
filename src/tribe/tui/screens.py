from __future__ import annotations

import json
import time
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from ..sessions import SessionStore
from ..sessions.messages import Role
from .widgets import COMMANDS, _clip


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


def _choice(label: str, key: str) -> Option:
    return Option(Content.assemble(label, (f"  {key}", "$text-muted")))


def _ago(timestamp: float) -> str:
    seconds = max(0, time.time() - timestamp)
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return f"{int(seconds // size)}{unit} ago"
    return "just now"


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
        with Vertical(id="approval-box", classes="dialog") as box:
            box.border_title = f"Allow {self.tool}?"
            yield Static(_action_detail(self.tool, self.args), id="approval-action", markup=False)
            yield OptionList(
                _choice("Yes", "y"),
                _choice(f"Yes, and always allow {self.tool} this session", "a"),
                _choice("No", "n"),
                id="approval-options",
            )
            yield Static("↑/↓ to choose · enter to confirm · esc to deny", classes="dialog-keys")

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        [self.action_approve, self.action_always, self.action_deny][event.option_index]()

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
        with Vertical(classes="dialog") as box:
            box.border_title = "Sessions"
            yield Static(
                "type to filter · ↑/↓ to move · enter to open · esc to cancel",
                classes="dialog-hint",
            )
            yield Input(placeholder="filter…", id="session-filter")
            yield OptionList(id="sessions-list")

    def on_mount(self) -> None:
        self._populate("")
        self.query_one("#session-filter", Input).focus()

    def _populate(self, query: str) -> None:
        query = query.lower()
        option_list = self.query_one(OptionList)
        option_list.clear_options()
        for session_id, count, preview, last_ts in self.rows:
            text = (preview or "(empty)").replace("\n", " ")
            if query and query not in text.lower() and query not in session_id.lower():
                continue
            marker = ("● ", "$primary") if session_id == self.current_id else "  "
            label = Content.assemble(
                marker,
                (f"{_clip(text, 34):<36}", "$foreground"),
                (f"{count:>3} msgs  {_ago(last_ts) if last_ts else '':>8}  ", "$text-muted"),
                (session_id[:8], "$text-muted"),
            )
            option_list.add_option(Option(label, id=session_id))
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


KEYS = [
    ("enter", "send the message (or run the highlighted /command)"),
    ("shift+enter", "insert a newline (also ctrl+j)"),
    ("↑ / ↓", "previous / next prompt from history"),
    ("tab", "accept the highlighted /command"),
    ("esc", "close the menu, or interrupt the current turn"),
    ("ctrl+c", "interrupt the current turn"),
    ("ctrl+p", "command palette (themes and more)"),
    ("f1", "this help"),
    ("ctrl+q", "quit"),
]


def help_content() -> Content:
    lines = [Content.styled("Commands", "bold $primary")]
    lines += [Content.assemble((f"  {name:<14}", "bold"), (desc, "$text-muted")) for name, desc in COMMANDS]
    lines += [Content(""), Content.styled("Keys", "bold $primary")]
    lines += [Content.assemble((f"  {key:<14}", "bold"), (desc, "$text-muted")) for key, desc in KEYS]
    lines += [
        Content(""),
        Content.styled(
            "While the agent works you can keep typing — enter queues a follow-up,\n"
            "esc interrupts so you can redirect immediately.",
            "$text-muted",
        ),
    ]
    return Content("\n").join(lines)


class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        ("escape", "close", "Close"),
        ("q", "close", "Close"),
        ("enter", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog") as box:
            box.border_title = "Tribe · help"
            yield Static(help_content(), id="help-body")
            yield Static("esc or q to close", classes="dialog-keys")

    def action_close(self) -> None:
        self.dismiss(None)
