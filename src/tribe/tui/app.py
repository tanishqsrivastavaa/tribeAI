from __future__ import annotations

import os
import time
import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Callable, Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.content import Content
from textual.theme import Theme
from textual.widgets import OptionList, Static

from .. import config
from ..agent import AgentLoop
from ..agent.limits import Cancellation
from ..models import DEFAULT_PROVIDER, PROVIDERS
from ..observability import Observer
from ..sessions import SessionStore
from ..sessions.messages import Message, Role, ToolStatus
from . import messages as m
from .approval import TuiApprover
from .composer import Composer
from .login import ApiKeyScreen, ModelSelectScreen, ProviderSelectScreen
from .observer import TuiObserver
from .screens import HelpScreen, SessionsScreen
from .widgets import (
    COMMANDS,
    ActivityLine,
    AssistantMessage,
    Banner,
    CommandMenu,
    EventLine,
    StatusBar,
    ToolActivity,
    UserMessage,
    format_duration,
)

LoopFactory = Callable[[Observer, object, Optional[str], Optional[str]], AgentLoop]

TRIBE_THEME = Theme(
    name="tribe",
    primary="#B9A6FF",
    secondary="#7CCFEA",
    accent="#7CCFEA",
    warning="#F0C674",
    error="#F2837B",
    success="#8BD3A3",
    foreground="#E6E6EA",
    background="#121214",
    surface="#18181B",
    panel="#222227",
    variables={
        "markdown-h1-color": "#B9A6FF",
        "markdown-h1-background": "transparent",
        "markdown-h1-text-style": "bold",
        "markdown-h2-color": "#B9A6FF",
        "markdown-h2-text-style": "bold",
        "markdown-h3-color": "#7CCFEA",
        "markdown-h3-text-style": "bold",
        "markdown-h4-color": "#E6E6EA",
        "markdown-h5-color": "#E6E6EA",
        "markdown-h6-color": "#E6E6EA",
        "markdown-h6-text-style": "bold",
        "scrollbar": "#2C2C33",
        "scrollbar-hover": "#3A3A43",
        "scrollbar-active": "#B9A6FF",
        "scrollbar-background": "#121214",
        "scrollbar-background-hover": "#121214",
        "scrollbar-background-active": "#121214",
        "block-cursor-background": "#B9A6FF 25%",
        "block-cursor-foreground": "#E6E6EA",
        "block-cursor-blurred-background": "#B9A6FF 15%",
        "text-muted": "#8E8E99",
    },
)


def _display_path(path: Path) -> str:
    home = str(Path.home())
    text = str(path)
    return "~" + text[len(home):] if text == home or text.startswith(home + os.sep) else text


def _git_branch(path: Path) -> str:
    git = next((d / ".git" for d in (path, *path.parents) if (d / ".git").exists()), None)
    try:
        ref = (git / "HEAD").read_text().strip() if git else ""
    except OSError:
        return ""
    return ref.removeprefix("ref: refs/heads/") if ref.startswith("ref:") else ref[:7]


def _version() -> str:
    metadata = Path(__file__).resolve().parents[3] / "pyproject.toml"
    try:
        with metadata.open("rb") as file:
            return str(tomllib.load(file)["project"]["version"])
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        pass
    try:
        return version("tribeai")
    except PackageNotFoundError:
        return ""


class TribeApp(App):
    CSS = """
    Screen { background: $background; }

    #transcript {
        height: 1fr;
        padding: 1 2 0 2;
        scrollbar-size-vertical: 1;
    }
    Banner {
        width: auto;
        max-width: 100%;
        height: auto;
        text-wrap: nowrap;
        text-overflow: ellipsis;
        border: round $primary 45%;
        padding: 1 2;
        margin: 0 0 1 0;
    }
    .user-msg {
        background: $panel;
        padding: 1 2;
        margin: 1 0;
    }
    .assistant-msg { padding: 0 1 0 2; margin: 1 0 0 0; background: transparent; }
    .assistant-msg > MarkdownBlock { margin: 1 0 0 0; }
    .assistant-msg > MarkdownBlock:first-child { margin-top: 0; }
    .assistant-msg MarkdownH1 { content-align: left middle; }
    .assistant-msg MarkdownFence { background: $surface; }
    .event-line { padding: 0 0 0 2; margin: 1 0 0 0; color: $text-muted; }
    .event-success { color: $success; }
    .event-warning { color: $warning; }
    .event-error { color: $error; }

    .tool {
        height: auto;
        border: none;
        background: transparent;
        padding: 0 0 0 1;
        margin: 0;
    }
    .tool > CollapsibleTitle { padding: 0 1 0 0; color: $foreground; }
    .tool > CollapsibleTitle:focus { background: $boost; color: $foreground; text-style: none; }
    .tool > Contents { padding: 0 0 0 3; }
    .tool-output {
        color: $text-muted;
        border-left: vkey $foreground 15%;
        padding: 0 0 0 1;
    }

    #command-menu {
        height: auto;
        max-height: 8;
        margin: 0 1;
        padding: 0;
        border: round $primary 45%;
        background: transparent;
    }
    #command-menu > .option-list--option { padding: 0 1; }
    #command-menu > .option-list--option-highlighted {
        background: $primary 20%;
        color: $foreground;
        text-style: none;
    }

    #activity { height: 1; padding: 0 2; }
    #composer-box {
        height: auto;
        margin: 0 1;
        padding: 0 1;
        border: round $foreground 20%;
        border-subtitle-color: $text-muted;
        border-subtitle-align: right;
    }
    #composer-box:focus-within { border: round $primary 70%; }
    #prompt-glyph { width: 2; color: $primary; text-style: bold; }
    #prompt, #prompt:focus {
        height: auto;
        max-height: 10;
        border: none;
        padding: 0;
        background: transparent;
    }
    #status-bar { height: 1; padding: 0 2; }

    ModalScreen { align: center middle; background: $background 70%; }
    .dialog {
        width: 76;
        max-width: 90%;
        height: auto;
        max-height: 85%;
        padding: 1 2;
        border: round $primary 70%;
        border-title-color: $foreground;
        border-title-style: bold;
        background: $surface;
    }
    .dialog-hint { color: $text-muted; padding-bottom: 1; }
    .dialog-keys { color: $text-muted; padding-top: 1; }
    .dialog OptionList, .dialog Input { border: none; background: $panel; padding: 0; }
    .dialog OptionList:focus, .dialog Input:focus { background-tint: transparent; }
    .dialog OptionList > .option-list--option { padding: 0 1; }
    .dialog OptionList { max-height: 15; }
    .dialog Input { height: 1; padding: 0 1; }
    #approval-box { border: round $warning; }
    #approval-action { background: $panel; padding: 1 2; margin-bottom: 1; }
    #login-error { color: $error; }
    #session-filter { margin-bottom: 1; }
    """

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+c", "cancel", "Interrupt"),
        ("f1", "help", "Help"),
    ]

    def __init__(
        self,
        loop_factory: LoopFactory,
        store: SessionStore,
        session_id: str,
        model_name: str = "",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        workspace: str = ".",
    ) -> None:
        super().__init__()
        self._loop_factory = loop_factory
        self.store = store
        self.session_id = session_id
        self.model_name = model_name
        self.provider = provider
        self.model = model
        self.workspace = Path(workspace).resolve()
        self.loop: AgentLoop | None = None
        self.cancellation: Cancellation | None = None
        self._turn_active = False
        self._turn_started = 0.0
        self._queued: list[str] = []
        self._observer: Observer | None = None
        self._approver: TuiApprover | None = None
        self._menu: CommandMenu | None = None
        self._banner: Banner | None = None
        self._current_tool: ToolActivity | None = None
        self._pending_provider: str | None = None
        self._pending_key: str | None = None

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="transcript")
        yield ActivityLine()
        with Horizontal(id="composer-box"):
            yield Static("❯", id="prompt-glyph")
            yield Composer(id="prompt")
        yield StatusBar()

    def on_mount(self) -> None:
        self.register_theme(TRIBE_THEME)
        self.theme = "tribe"
        self.title = "Tribe"
        self._observer = TuiObserver(self)
        self._approver = TuiApprover(self)
        self.watch(self._transcript, "virtual_size", self._on_transcript_grow, init=False)
        self._reset_transcript()
        try:
            self.render_history(self.store.load(self.session_id))
        except FileNotFoundError:
            pass
        self._build_loop()
        self._refresh_status()
        self.query_one("#prompt", Composer).focus()

    # ---------- accessors ----------

    @property
    def _transcript(self) -> VerticalScroll:
        return self.query_one("#transcript", VerticalScroll)

    @property
    def _activity(self) -> ActivityLine:
        return self.query_one(ActivityLine)

    def _mount(self, widget) -> None:
        self._transcript.mount(widget)

    def _on_transcript_grow(self) -> None:
        self.call_after_refresh(self._follow)

    def _follow(self, force: bool = False) -> None:
        # Anchoring content shorter than the viewport bottom-aligns it, so wait for overflow.
        transcript = self._transcript
        if transcript.max_scroll_y > 0 and (force or not transcript.is_anchored):
            transcript.anchor()

    def _reset_transcript(self) -> None:
        self._transcript.anchor(False)
        self._transcript.remove_children()
        self._banner = Banner(_version())
        self._mount(self._banner)

    def transcript_text(self) -> str:
        parts = []
        for child in self._transcript.children:
            value = getattr(child, "text_value", None)
            if value:
                parts.append(value)
        return "\n".join(parts)

    # ---------- status ----------

    def _refresh_status(self) -> None:
        limit = self.loop.model.context_limit if self.loop is not None else 0
        branch = _git_branch(self.workspace)
        self.query_one(StatusBar).set(
            workspace=_display_path(self.workspace),
            branch=branch,
            session=self.session_id,
            context_limit=limit,
        )
        if self.loop is not None:
            model = Content.assemble(
                (self.model_name, "$foreground"), (f" · {self.provider}", "$text-muted")
            )
        else:
            model = Content.from_markup("[$warning]not logged in[/] [$text-muted]· type /login")
        self.query_one("#composer-box").border_subtitle = model
        if self._banner is not None:
            where = Content(_display_path(self.workspace))
            if branch:
                where = Content.assemble(where, (f"  ⎇ {branch}", "$secondary"))
            self._banner.set_rows(
                [
                    ("model", model),
                    ("workspace", where),
                    ("session", Content.styled(self.session_id[:8], "$text-muted")),
                ]
            )
        self._refresh_hint()

    def _refresh_hint(self) -> None:
        parts = []
        if self._queued:
            parts.append(f"{len(self._queued)} queued")
        if self._turn_active:
            parts.append("esc to interrupt")
        self._activity.set_hint(" · ".join(parts))

    # ---------- model / login wiring ----------

    def _build_loop(self) -> bool:
        if not config.has_credentials(self.provider or DEFAULT_PROVIDER):
            self.loop = None
            return False
        try:
            self.loop = self._loop_factory(
                self._observer, self._approver, self.provider, self.model
            )
        except Exception as exc:  # noqa: BLE001
            self.loop = None
            self._mount(EventLine(f"could not initialize model: {exc}", "error"))
            return False
        self.model_name = self.loop.model.name
        if self.provider is None:
            self.provider = DEFAULT_PROVIDER
        return True

    # ---------- history replay ----------

    def render_history(self, history: list[Message]) -> None:
        pending: dict[str, ToolActivity] = {}
        for msg in history:
            if msg.role == Role.USER:
                self._mount(UserMessage(msg.content))
            elif msg.role == Role.ASSISTANT and msg.content:
                self._mount(AssistantMessage(msg.content))
            elif msg.role == Role.TOOL_CALL:
                tool = ToolActivity(msg.tool_name or "tool", msg.arguments or {})
                pending[msg.call_id or ""] = tool
                self._mount(tool)
            elif msg.role == Role.TOOL_RESULT:
                tool = pending.pop(msg.call_id or "", None)
                is_error = msg.status == ToolStatus.ERROR
                if tool is not None:
                    tool.finalize(is_error, msg.error, msg.result or "", 0.0)
            elif msg.role == Role.SUMMARY:
                self._mount(EventLine(f"↯ compacted earlier history ({len(msg.content)} chars)"))

    # ---------- input ----------

    def on_text_area_changed(self, event) -> None:
        self._sync_menu(event.text_area.text)

    def _sync_menu(self, text: str) -> None:
        if not (text.startswith("/") and " " not in text):
            self._drop_menu()
            return
        if self._menu is None:
            self._menu = CommandMenu(COMMANDS)
            self.mount(self._menu, before=self._activity)
            self.query_one("#prompt", Composer).set_menu(self._menu)
        self._menu.update_query(text)
        if not self._menu.active:
            self._drop_menu()

    def _drop_menu(self) -> None:
        if self._menu is not None:
            self._menu.remove()
            self._menu = None
            self.query_one("#prompt", Composer).set_menu(None)

    @on(OptionList.OptionSelected, "#command-menu")
    def _on_menu_click(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        if self._menu is not None and self._menu.matches:
            command = self._menu.matches[event.option_index][0]
            self.query_one("#prompt", Composer).value = ""
            self._drop_menu()
            self._handle_command(command)

    def on_composer_submitted(self, event: Composer.Submitted) -> None:
        text = event.value.strip()
        self._drop_menu()
        if not text:
            return
        if text.startswith("/"):
            self._handle_command(text)
            return
        if self.loop is None:
            self._mount(EventLine("No model configured — type /login first.", "warning"))
            return
        if self._turn_active:
            self._queued.append(text)
            self._mount(EventLine(f"⧗ queued — will send after this turn: {text}"))
            self._refresh_hint()
            return
        self._start_turn(text)

    def _handle_command(self, text: str) -> None:
        command = text[1:].split()[0].lower()
        if command == "login":
            self.push_screen(ProviderSelectScreen(), self._on_provider_chosen)
        elif command == "model":
            self._start_model_change()
        elif command == "sessions":
            self._start_sessions()
        elif command == "new":
            self._start_new_session()
        elif command == "clear":
            self._reset_transcript()
            self._refresh_status()
        elif command == "help":
            self.push_screen(HelpScreen())
        else:
            self._mount(EventLine(f"unknown command: /{command}", "warning"))

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    # ---------- login flow ----------

    def _on_provider_chosen(self, provider: str | None) -> None:
        if not provider:
            return
        self._pending_provider = provider
        self.push_screen(ApiKeyScreen(provider), self._on_key_entered)

    def _on_key_entered(self, key: str | None) -> None:
        if key is None:
            return
        self._pending_key = key
        self.push_screen(ModelSelectScreen(self._pending_provider), self._on_model_chosen)

    def _on_model_chosen(self, model: str | None) -> None:
        if not model:
            return
        self._apply_login(self._pending_provider, self._pending_key, model)

    def _apply_login(self, provider: str, key: str, model: str) -> None:
        env_var = PROVIDERS[provider].api_key_env
        if key and env_var:
            os.environ[env_var] = key
        self.provider = provider
        self.model = model
        if self._build_loop():
            config.remember_credentials(provider, model, key or None)
            self._mount(
                EventLine(f"✓ logged in — {provider} · {self.model_name} (saved)", "success")
            )
        self._refresh_status()
        self.query_one("#prompt", Composer).focus()

    def _start_model_change(self) -> None:
        if not self.provider:
            self._mount(EventLine("No provider yet — type /login first.", "warning"))
            return
        self.push_screen(
            ModelSelectScreen(self.provider, current=self.model_name),
            self._on_model_only_chosen,
        )

    def _on_model_only_chosen(self, model: str | None) -> None:
        if not model:
            return
        self.model = model
        if self._build_loop():
            config.remember_credentials(self.provider, model)
            self._mount(EventLine(f"✓ model set — {self.model_name}", "success"))
        self._refresh_status()
        self.query_one("#prompt", Composer).focus()

    # ---------- sessions ----------

    def _start_sessions(self) -> None:
        if not self.store.list_sessions():
            self._mount(EventLine("no saved sessions", "warning"))
            return
        self.push_screen(SessionsScreen(self.store, self.session_id), self._on_session_chosen)

    def _on_session_chosen(self, session_id: str | None) -> None:
        if not session_id or session_id == self.session_id:
            return
        self.session_id = session_id
        self._reset_transcript()
        try:
            self.render_history(self.store.load(session_id))
        except FileNotFoundError:
            pass
        self._refresh_status()
        self.query_one("#prompt", Composer).focus()

    def _start_new_session(self) -> None:
        self.session_id = self.store.create()
        self._reset_transcript()
        self._mount(EventLine(f"started new session {self.session_id[:8]}"))
        self._refresh_status()

    # ---------- turn lifecycle ----------

    def _start_turn(self, text: str) -> None:
        self._turn_active = True
        self._turn_started = time.monotonic()
        self.cancellation = Cancellation()
        self._current_tool = None
        self._mount(UserMessage(text))
        self.call_after_refresh(self._follow, True)
        self._activity.start("Thinking")
        self._refresh_hint()
        self._run_turn(text)

    @work(thread=True)
    def _run_turn(self, text: str) -> None:
        assert self.loop is not None
        try:
            self.loop.run(self.session_id, text, self.cancellation)
        except Exception as exc:  # noqa: BLE001
            self.post_message(m.RunFailed(f"{type(exc).__name__}: {exc}"))

    def action_cancel(self) -> None:
        if self._turn_active and self.cancellation is not None and not self.cancellation.cancelled:
            self.cancellation.cancel()
            self._activity.start("Interrupting")
            self._mount(EventLine("interrupting… (edit the prompt and send to redirect)", "warning"))

    def _finish_turn(self) -> None:
        self._turn_active = False
        self._current_tool = None
        self._activity.stop()
        self._refresh_status()
        self.query_one("#prompt", Composer).focus()
        if self._queued and self.loop is not None:
            self._start_turn(self._queued.pop(0))

    # ---------- run events ----------

    def on_run_started(self, message: m.RunStarted) -> None:
        pass

    def on_model_activity(self, message: m.ModelActivity) -> None:
        self.query_one(StatusBar).set(est_tokens=message.estimated_tokens)
        if not (self.cancellation and self.cancellation.cancelled):
            self._activity.start("Thinking")

    def on_assistant_text(self, message: m.AssistantText) -> None:
        self._mount(AssistantMessage(message.text))

    def on_approval_requested(self, message: m.ApprovalRequested) -> None:
        tool = ToolActivity(message.tool, message.args)
        tool.set_awaiting()
        self._current_tool = tool
        self._mount(tool)
        self._activity.start("Waiting for approval")

    def on_tool_started(self, message: m.ToolStarted) -> None:
        if self._current_tool is not None and self._current_tool.state == "awaiting":
            self._current_tool.set_running()
        else:
            tool = ToolActivity(message.name, message.args)
            self._current_tool = tool
            self._mount(tool)
        self._activity.start(f"Running {message.name}")

    def on_tool_ended(self, message: m.ToolEnded) -> None:
        if self._current_tool is not None:
            self._current_tool.finalize(
                message.is_error, message.error, message.output, message.duration
            )
            self._current_tool = None

    def on_approval_resolved(self, message: m.ApprovalResolved) -> None:
        if message.allowed:
            return
        if self._current_tool is not None and self._current_tool.state == "awaiting":
            self._current_tool.set_denied(message.reason)
            self._current_tool = None
        else:
            self._mount(EventLine(f"⊘ {message.tool} denied: {message.reason}", "warning"))

    def on_compacted(self, message: m.Compacted) -> None:
        self._mount(EventLine(f"↯ compacted history ({message.size} chars)"))

    def on_run_ended(self, message: m.RunEnded) -> None:
        if message.completed:
            elapsed = format_duration(time.monotonic() - self._turn_started)
            self._mount(EventLine(f"◆ done in {elapsed}"))
        else:
            self._mount(EventLine(f"■ stopped: {message.status}", "warning"))
        self._finish_turn()

    def on_run_failed(self, message: m.RunFailed) -> None:
        self._mount(EventLine(f"⚠ model error: {message.error}", "error"))
        self._mount(
            EventLine(
                "The request failed — /login to update your key, or /model to switch.", "warning"
            )
        )
        self._finish_turn()
