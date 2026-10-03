from __future__ import annotations

import time
from typing import Any

from textual.color import Color
from textual.content import Content
from textual.widget import Widget
from textual.widgets import Collapsible, Markdown, OptionList, Static
from textual.widgets.option_list import Option

_MAX_OUTPUT_LINES = 200
_MAX_OUTPUT_CHARS = 8000
_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_WORDMARK = ("▀█▀ █▀▄ █ █▀▄ █▀▀", " █  █▀▄ █ █▀▄ █▀ ", " ▀  ▀ ▀ ▀ ▀▀  ▀▀▀")

COMMANDS = [
    ("/login", "provider, API key, and model"),
    ("/model", "switch the active model"),
    ("/sessions", "browse and resume sessions"),
    ("/new", "start a fresh session"),
    ("/clear", "clear the transcript view"),
    ("/help", "keys and commands"),
]

_GLYPH = {
    "awaiting": ("◌", "$warning"),
    "running": ("●", "$secondary"),
    "ok": ("✓", "$success"),
    "error": ("✗", "$error"),
    "denied": ("⊘", "$warning"),
}


def format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def _clip(value: Any, limit: int = 68) -> str:
    text = str(value).replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _spread(left: Content, right: Content, width: int) -> Content:
    gap = max(1, width - left.cell_length - right.cell_length)
    return Content.assemble(left, " " * gap, right)


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
        self._output = Static(" ", classes="tool-output", markup=False)
        super().__init__(
            self._output,
            title=self._title_text(),
            collapsed=True,
            collapsed_symbol="",
            expanded_symbol="",
        )
        self.add_class("tool")

    def _title_text(self) -> Content:
        glyph, color = _GLYPH[self.state]
        verb, _, target = tool_summary(self.tool_name, self.args).partition(" ")
        meta = (f"  {self._meta}", "$text-muted") if self._meta else ""
        return Content.assemble((glyph, color), " ", (verb, "bold"), " ", target, meta)

    def _apply_state(self) -> None:
        for name in _GLYPH:
            self.remove_class(f"tool-{name}")
        self.add_class(f"tool-{self.state}")
        self.title = self._title_text()

    @property
    def text_value(self) -> str:
        head = f"{self.state} {tool_summary(self.tool_name, self.args)} {self._meta}"
        return f"{head}\n{self._output_text}".strip()

    def on_mount(self) -> None:
        self._apply_state()

    def set_awaiting(self) -> None:
        self.state = "awaiting"
        self._meta = "awaiting approval"
        self._apply_state()

    def set_running(self) -> None:
        self.state = "running"
        self._meta = ""
        self._apply_state()

    def set_denied(self, reason: str) -> None:
        self.state = "denied"
        self._meta = f"denied — {reason}"
        self._apply_state()

    def finalize(
        self, is_error: bool, error: str | None, output: str, duration: float
    ) -> None:
        self.state = "error" if is_error else "ok"
        if is_error and error and error not in (output or ""):
            body = error + (("\n\n" + output) if output else "")
        else:
            body = output or ""
        self._output_text = body

        parts = [format_duration(duration)]
        if is_error and error:
            parts.insert(0, _clip(error, 48))
        elif body:
            count = len(body.splitlines())
            parts.insert(0, f"{count} line" + ("" if count == 1 else "s"))
        self._meta = " · ".join(parts)

        clipped, hidden = _clip_output(body)
        if clipped:
            if hidden:
                clipped += f"\n… ({hidden} more lines)"
            self._output.update(clipped)
            if is_error:
                self.collapsed = False
        else:
            self._output.update(Content.styled("(no output)", "$text-muted"))
        self._apply_state()


class UserMessage(Static):
    def __init__(self, content: str) -> None:
        self.text_value = content
        super().__init__(Content.assemble(("❯ ", "bold $primary"), content), classes="user-msg")


class AssistantMessage(Markdown):
    def __init__(self, content: str) -> None:
        self.text_value = content
        super().__init__(content, classes="assistant-msg")


class EventLine(Static):
    """A subtle one-liner: compaction, stop notices, system hints. kind: muted|success|warning|error."""

    def __init__(self, text: str, kind: str = "muted") -> None:
        self.text_value = text
        super().__init__(Content(text), classes=f"event-line event-{kind}")


class Banner(Widget):
    """Welcome card: gradient wordmark beside the session facts."""

    def __init__(self, version: str = "") -> None:
        super().__init__()
        self.version = version
        self.rows: list[tuple[str, Content]] = []

    def set_rows(self, rows: list[tuple[str, Content]]) -> None:
        self.rows = rows
        self.refresh(layout=True)

    def render(self) -> Content:
        theme = self.app.current_theme
        start = Color.parse(theme.primary)
        end = Color.parse(theme.secondary or theme.primary)
        width = len(_WORDMARK[0])
        marks = [
            Content.assemble(
                *((ch, f"bold {start.blend(end, x / width).hex}") for x, ch in enumerate(line))
            )
            for line in _WORDMARK
        ]
        marks.append(Content.styled(f"v{self.version}".ljust(width) if self.version else "", "$text-muted"))
        lines = []
        for i in range(max(len(marks), len(self.rows))):
            mark = marks[i] if i < len(marks) else Content("")
            line = Content.assemble(mark, " " * (width - mark.cell_length + 4))
            if i < len(self.rows):
                label, value = self.rows[i]
                line = Content.assemble(line, (f"{label:<11}", "$text-muted"), value)
            lines.append(line)
        tip = Content.from_markup(
            "[$text-muted]type [b $foreground]/[/] for commands · "
            "[b $foreground]shift+enter[/] for a newline · [b $foreground]F1[/] for help"
        )
        return Content("\n").join([*lines, Content(""), tip])


class ActivityLine(Widget):
    """The live 'working' row above the composer: spinner, label, elapsed, hint."""

    def __init__(self) -> None:
        super().__init__(id="activity")
        self.label = ""
        self.hint = ""
        self.started = 0.0
        self._timer = None

    def start(self, label: str) -> None:
        self.label = label
        if self._timer is None:
            self.started = time.monotonic()
            self._timer = self.set_interval(1 / 12, self.refresh)
        self.refresh()

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        self.label = ""
        self.refresh()

    def set_hint(self, hint: str) -> None:
        self.hint = hint
        self.refresh()

    def render(self) -> Content:
        right = Content.styled(self.hint, "$text-muted")
        if not self.label:
            return _spread(Content(""), right, self.size.width)
        elapsed = time.monotonic() - self.started
        frame = _SPINNER[int(elapsed * 12) % len(_SPINNER)]
        left = Content.assemble(
            (f"{frame} ", "bold $primary"),
            (f"{self.label}… ", "$foreground"),
            (f"{int(elapsed)}s", "$text-muted"),
        )
        return _spread(left, right, self.size.width)


class StatusBar(Widget):
    """The quiet line under the composer: where you are, which session, how full the context is."""

    def __init__(self) -> None:
        super().__init__(id="status-bar")
        self.workspace = ""
        self.branch = ""
        self.session = ""
        self.est_tokens = 0
        self.context_limit = 0

    def set(self, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(self, key, value)
        self.refresh()

    def render(self) -> Content:
        left = [(self.workspace, "$text-muted")]
        if self.branch:
            left.append((f" ⎇ {self.branch}", "$secondary"))
        if self.session:
            left.append((f" · {self.session[:8]}", "$text-muted"))
        right = [("F1 help", "$text-muted")]
        if self.context_limit:
            pct = min(100, int(self.est_tokens / self.context_limit * 100))
            right[:0] = [(f"ctx {pct}%", "$warning" if pct >= 60 else "$text-muted"), "  ·  "]
        return _spread(Content.assemble(*left), Content.assemble(*right), self.size.width)


class CommandMenu(OptionList, can_focus=False):
    """A compact, filtered list of slash commands shown above the composer."""

    def __init__(self, commands: list[tuple[str, str]]) -> None:
        super().__init__(id="command-menu")
        self.commands = commands
        self.matches: list[tuple[str, str]] = []

    @property
    def active(self) -> bool:
        return bool(self.matches)

    def update_query(self, text: str) -> None:
        if text.startswith("/") and " " not in text:
            query = text[1:].lower()
            self.matches = [c for c in self.commands if c[0][1:].startswith(query)]
        else:
            self.matches = []
        self.set_options(
            Option(Content.assemble((f"{name:<12}", "bold"), (desc, "$text-muted")))
            for name, desc in self.matches
        )
        if self.matches:
            self.highlighted = 0
        self.display = self.active

    def move(self, delta: int) -> None:
        if self.matches:
            self.highlighted = ((self.highlighted or 0) + delta) % len(self.matches)

    def selected(self) -> str | None:
        if not self.matches or self.highlighted is None:
            return None
        return self.matches[self.highlighted][0]
