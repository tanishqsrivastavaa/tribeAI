from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.widgets import Collapsible, Markdown, Static

_MAX_OUTPUT_LINES = 200
_MAX_OUTPUT_CHARS = 8000

_GLYPH = {
    "awaiting": ("◌", "yellow"),
    "running": ("▸", "cyan"),
    "ok": ("✓", "green"),
    "error": ("✗", "red"),
    "denied": ("⊘", "yellow"),
}


def format_duration(seconds: float) -> str:
    ms = seconds * 1000
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{seconds:.1f}s"


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def _clip(value: Any, limit: int = 68) -> str:
    text = str(value).replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def tool_summary(name: str, args: dict[str, Any]) -> str:
    """A dense, human one-liner describing a tool call."""
    args = args or {}
    if name == "read":
        return f"read {_clip(args.get('path', ''))}"
    if name == "write":
        return f"write {_clip(args.get('path', ''))}"
    if name == "grep":
        where = args.get("path") or "."
        return f"grep {_clip(args.get('pattern', ''), 40)!r} in {_clip(where, 24)}"
    if name == "bash":
        return f"$ {_clip(args.get('command', ''), 72)}"
    for key in ("path", "command", "pattern"):
        if key in args:
            return f"{name} {_clip(args[key])}"
    return f"{name} {_clip(args)}"


def _clip_output(text: str) -> tuple[str, int]:
    if not text:
        return "", 0
    lines = text.splitlines()
    hidden = 0
    if len(lines) > _MAX_OUTPUT_LINES:
        hidden = len(lines) - _MAX_OUTPUT_LINES
        lines = lines[:_MAX_OUTPUT_LINES]
    clipped = "\n".join(lines)
    if len(clipped) > _MAX_OUTPUT_CHARS:
        clipped = clipped[:_MAX_OUTPUT_CHARS]
        hidden = max(hidden, 1)
    return clipped, hidden


class ToolActivity(Collapsible):
    """A first-class tool call: status glyph + dense summary as the collapsible title."""

    def __init__(self, name: str, args: dict[str, Any]) -> None:
        self.tool_name = name
        self.args = args or {}
        self.state = "running"
        self._meta = ""
        self._output_text = ""
        self._output = Static(Text(" "), classes="tool-output", markup=False)
        super().__init__(self._output, title=self._title_text(), collapsed=True)
        self.add_class("tool")

    def _title_text(self) -> str:
        glyph, _ = _GLYPH.get(self.state, ("·", "white"))
        summary = tool_summary(self.tool_name, self.args)
        return f"{glyph} {summary}  {self._meta}".rstrip()

    def _apply_state_class(self) -> None:
        for name in ("tool-awaiting", "tool-running", "tool-ok", "tool-error", "tool-denied"):
            self.remove_class(name)
        self.add_class(f"tool-{self.state}")

    @property
    def text_value(self) -> str:
        head = f"{self.state} {tool_summary(self.tool_name, self.args)} {self._meta}"
        return f"{head}\n{self._output_text}".strip()

    def on_mount(self) -> None:
        self._apply_state_class()
        self.title = self._title_text()

    def set_awaiting(self) -> None:
        self.state = "awaiting"
        self._meta = "awaiting approval"
        self.title = self._title_text()
        self._apply_state_class()

    def set_running(self) -> None:
        self.state = "running"
        self._meta = ""
        self.title = self._title_text()
        self._apply_state_class()

    def set_denied(self, reason: str) -> None:
        self.state = "denied"
        self._meta = f"denied — {reason}"
        self.title = self._title_text()
        self._apply_state_class()

    def finalize(
        self, is_error: bool, error: str | None, output: str, duration: float
    ) -> None:
        self.state = "error" if is_error else "ok"
        parts = [format_duration(duration)]
        if is_error and error:
            parts.insert(0, _clip(error, 48))
        self._meta = " · ".join(p for p in parts if p)

        body = ""
        if is_error and error and error not in (output or ""):
            body = error + (("\n\n" + output) if output else "")
        else:
            body = output or ""
        self._output_text = body

        clipped, hidden = _clip_output(body)
        if clipped:
            if hidden:
                clipped += f"\n… ({hidden} more lines)"
            self._output.update(clipped)
            if is_error:
                self.collapsed = False
        else:
            self._output.update(Text("(no output)", style="dim"))
        self.title = self._title_text()
        self._apply_state_class()


class UserMessage(Static):
    def __init__(self, content: str) -> None:
        self.text_value = content
        text = Text()
        text.append("› ", style="bold cyan")
        text.append(content)
        super().__init__(text, classes="user-msg", markup=False)


class AssistantMessage(Markdown):
    def __init__(self, content: str) -> None:
        self.text_value = content
        super().__init__(content, classes="assistant-msg")


class EventLine(Static):
    """A subtle, dim one-liner: compaction, stop notices, system hints."""

    def __init__(self, text: str, style: str = "dim") -> None:
        self.text_value = text
        super().__init__(Text(text, style=style), classes="event-line", markup=False)


class CommandMenu(Static):
    """A compact, filtered list of slash commands shown above the composer."""

    def __init__(self, commands: list[tuple[str, str]]) -> None:
        super().__init__(Text(" "), classes="command-menu", markup=False)
        self.commands = commands
        self.matches: list[tuple[str, str]] = []
        self.index = 0
        self._open = False

    def _hide(self) -> None:
        self._open = False
        self.matches = []
        self.update(Text(" "))

    @property
    def active(self) -> bool:
        return self._open and bool(self.matches)

    def update_query(self, text: str) -> None:
        if not text.startswith("/") or " " in text:
            # no command context, or a full command plus an argument is typed
            self._hide()
            return
        query = text[1:].split(" ", 1)[0].lower()
        matches = [c for c in self.commands if c[0][1:].startswith(query)]
        if not matches:
            self._hide()
            return
        self.matches = matches
        self.index = min(self.index, len(self.matches) - 1)
        self._open = True
        self._render_options()

    def move(self, delta: int) -> None:
        if not self.matches:
            return
        self.index = (self.index + delta) % len(self.matches)
        self._render_options()

    def selected(self) -> str | None:
        if not self.matches:
            return None
        return self.matches[self.index][0]

    def _render_options(self) -> None:
        out = Text()
        for i, (name, desc) in enumerate(self.matches):
            selected = i == self.index
            out.append("› " if selected else "  ", style="cyan")
            out.append(f"{name:<12}", style="bold" if selected else "white")
            out.append(desc, style="dim")
            if i != len(self.matches) - 1:
                out.append("\n")
        self.update(out)


class StatusBar(Static):
    def __init__(self) -> None:
        super().__init__(Text(" "), classes="status-bar", markup=False)
        self.state = "idle"
        self.model = ""
        self.session = ""
        self.est_tokens = 0
        self.context_limit = 0

    _STATE_GLYPH = {
        "idle": ("◇", "dim"),
        "working": ("●", "cyan"),
        "awaiting": ("◌", "yellow"),
        "interrupting": ("■", "yellow"),
        "error": ("✗", "red"),
        "offline": ("○", "dim"),
    }

    def set(self, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(self, key, value)
        self.refresh_bar()

    def refresh_bar(self) -> None:
        glyph, color = self._STATE_GLYPH.get(self.state, ("◇", "dim"))
        line = Text()
        line.append(f"{glyph} ", style=color)
        line.append(f"{self.state:<12}", style=color)
        line.append(self.model or "no model", style="bold" if self.model else "dim")
        if self.context_limit:
            pct = min(100, int(self.est_tokens / self.context_limit * 100))
            line.append(f"   ctx {pct}%", style="yellow" if pct >= 60 else "dim")
        if self.session:
            line.append(f"   {self.session[:8]}", style="dim")
        self.update(line)
