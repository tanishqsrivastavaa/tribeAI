from __future__ import annotations

import os
from typing import Callable, Optional

from textual import work
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header

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
    AssistantMessage,
    CommandMenu,
    EventLine,
    StatusBar,
    ToolActivity,
    UserMessage,
)

LoopFactory = Callable[[Observer, object, Optional[str], Optional[str]], AgentLoop]

COMMANDS = [
    ("/login", "provider, API key, and model"),
    ("/model", "switch the active model"),
    ("/sessions", "browse and resume sessions"),
    ("/new", "start a fresh session"),
    ("/clear", "clear the transcript view"),
    ("/help", "keys and commands"),
]


class TribeApp(App):
    CSS = """
    #transcript { height: 1fr; padding: 0 1; }
    #transcript > * { margin: 0 0 1 0; }
    .user-msg { color: $text; }
    .assistant-msg { margin: 0 0 1 0; background: transparent; }
    .event-line { color: $text-muted; }
    .tool { height: auto; border: none; background: transparent; padding: 0; }
    .tool > CollapsibleTitle { padding: 0 1; color: $text-muted; }
    .tool-awaiting > CollapsibleTitle { color: $warning; }
    .tool-running > CollapsibleTitle { color: $accent; }
    .tool-ok > CollapsibleTitle { color: $success; }
    .tool-error > CollapsibleTitle { color: $error; }
    .tool-denied > CollapsibleTitle { color: $warning; }
    .tool-output { color: $text-muted; padding: 0 0 0 2; }

    #command-menu { height: auto; max-height: 8; background: $panel; padding: 0 1; }
    #status-bar { height: 1; background: $panel; padding: 0 1; }
    #prompt {
        height: auto;
        max-height: 10;
        border: round $primary-darken-2;
        padding: 0 1;
        background: $surface;
    }
    #prompt:focus { border: round $primary; }

    #approval-box {
        width: 70%;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        border: thick $warning;
        background: $surface;
    }
    ApprovalModal { align: center middle; }
    #approval-title { text-style: bold; padding-bottom: 1; }
    #approval-action { padding-bottom: 1; }
    #approval-keys { color: $text-muted; padding-top: 1; }
    ProviderSelectScreen, ApiKeyScreen, ModelSelectScreen, SessionsScreen, HelpScreen {
        align: center middle;
    }
    #login-box {
        width: 70%;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        border: thick $primary;
        background: $surface;
    }
    #login-title { text-style: bold; padding-bottom: 1; }
    #login-hint { color: $text-muted; padding-bottom: 1; }
    #login-error { color: $error; }
    #provider-list, #sessions-list { height: auto; max-height: 15; }
    #session-filter { margin-bottom: 1; }
    #help-body { height: auto; }
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
    ) -> None:
        super().__init__()
        self._loop_factory = loop_factory
        self.store = store
        self.session_id = session_id
        self.model_name = model_name
        self.provider = provider
        self.model = model
        self.loop: AgentLoop | None = None
        self.cancellation: Cancellation | None = None
        self._turn_active = False
        self._queued: list[str] = []
        self._observer: Observer | None = None
        self._approver: TuiApprover | None = None
        self._menu: CommandMenu | None = None
        self._current_tool: ToolActivity | None = None
        self._pending_provider: str | None = None
        self._pending_key: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(id="transcript")
        yield StatusBar()
        yield Composer(id="prompt")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Tribe"
        self._observer = TuiObserver(self)
        self._approver = TuiApprover(self)
        composer = self.query_one("#prompt", Composer)
        try:
            self.render_history(self.store.load(self.session_id))
        except FileNotFoundError:
            pass
        self._build_loop(initial=True)
        self._refresh_status()
        composer.focus()

    # ---------- accessors ----------

    @property
    def _transcript(self) -> VerticalScroll:
        return self.query_one("#transcript", VerticalScroll)

    def _mount(self, widget) -> None:
        self._transcript.mount(widget)
        self.call_after_refresh(self._transcript.scroll_end, animate=False)

    def transcript_text(self) -> str:
        parts = []
        for child in self._transcript.children:
            value = getattr(child, "text_value", None)
            if value:
                parts.append(value)
        return "\n".join(parts)

    # ---------- status ----------

    def _refresh_status(self) -> None:
        bar = self.query_one(StatusBar)
        if self.loop is None:
            state = "offline"
            limit = 0
        elif self._turn_active:
            state = bar.state if bar.state in ("working", "awaiting", "interrupting") else "working"
            limit = self.loop.model.context_limit
        else:
            state = "idle"
            limit = self.loop.model.context_limit
        bar.set(
            state=state,
            model=self.model_name,
            session=self.session_id,
            context_limit=limit,
        )
        self._update_subtitle()

    def _update_subtitle(self) -> None:
        state = self.model_name if self.loop is not None else "not logged in"
        self.sub_title = f"{self.session_id[:8]} · {state}".strip(" ·")

    # ---------- model / login wiring ----------

    def _build_loop(self, initial: bool = False) -> bool:
        if not config.has_credentials(self.provider or DEFAULT_PROVIDER):
            self.loop = None
            if initial:
                self._mount(
                    EventLine("Not logged in — type /login to add a provider API key.", "yellow")
                )
            self._update_subtitle()
            return False
        try:
            self.loop = self._loop_factory(
                self._observer, self._approver, self.provider, self.model
            )
        except Exception as exc:  # noqa: BLE001
            self.loop = None
            self._mount(EventLine(f"could not initialize model: {exc}", "red"))
            self._update_subtitle()
            return False
        self.model_name = self.loop.model.name
        if self.provider is None:
            self.provider = DEFAULT_PROVIDER
        self._update_subtitle()
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
            self.mount(self._menu, before=self.query_one(StatusBar))
            self.query_one("#prompt", Composer).set_menu(self._menu)
        self._menu.update_query(text)
        if not self._menu.active:
            self._drop_menu()

    def _drop_menu(self) -> None:
        if self._menu is not None:
            self._menu.remove()
            self._menu = None
            self.query_one("#prompt", Composer).set_menu(None)

    def on_composer_submitted(self, event: Composer.Submitted) -> None:
        text = event.value.strip()
        self._drop_menu()
        if not text:
            return
        if text.startswith("/"):
            self._handle_command(text)
            return
        if self.loop is None:
            self._mount(EventLine("No model configured — type /login first.", "yellow"))
            return
        if self._turn_active:
            self._queued.append(text)
            self._mount(EventLine(f"⧗ queued — will send after this turn: {text}"))
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
            self._transcript.remove_children()
        elif command == "help":
            self.push_screen(HelpScreen())
        else:
            self._mount(EventLine(f"unknown command: /{command}", "yellow"))

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
                EventLine(f"✓ logged in — {provider} · {self.model_name} (saved)", "green")
            )
        self._refresh_status()
        self.query_one("#prompt", Composer).focus()

    def _start_model_change(self) -> None:
        if not self.provider:
            self._mount(EventLine("No provider yet — type /login first.", "yellow"))
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
            self._mount(EventLine(f"✓ model set — {self.model_name}", "green"))
        self._refresh_status()
        self.query_one("#prompt", Composer).focus()

    # ---------- sessions ----------

    def _start_sessions(self) -> None:
        if not self.store.list_sessions():
            self._mount(EventLine("no saved sessions", "yellow"))
            return
        self.push_screen(SessionsScreen(self.store, self.session_id), self._on_session_chosen)

    def _on_session_chosen(self, session_id: str | None) -> None:
        if not session_id or session_id == self.session_id:
            return
        self.session_id = session_id
        self._transcript.remove_children()
        try:
            self.render_history(self.store.load(session_id))
        except FileNotFoundError:
            pass
        self._refresh_status()
        self.query_one("#prompt", Composer).focus()

    def _start_new_session(self) -> None:
        self.session_id = self.store.create()
        self._transcript.remove_children()
        self._mount(EventLine(f"started new session {self.session_id[:8]}"))
        self._refresh_status()

    # ---------- turn lifecycle ----------

    def _start_turn(self, text: str) -> None:
        self._turn_active = True
        self.cancellation = Cancellation()
        self._current_tool = None
        self._mount(UserMessage(text))
        self.query_one(StatusBar).set(state="working")
        self._refresh_status()
        self._run_turn(text)

    @work(thread=True)
    def _run_turn(self, text: str) -> None:
        assert self.loop is not None
        try:
            self.loop.run(self.session_id, text, self.cancellation)
        except Exception as exc:  # noqa: BLE001
            self.post_message(m.RunFailed(f"{type(exc).__name__}: {exc}"))

    def action_cancel(self) -> None:
        if self._turn_active and self.cancellation is not None:
            self.cancellation.cancel()
            self.query_one(StatusBar).set(state="interrupting")
            self._mount(EventLine("interrupting… (edit the prompt and send to redirect)", "yellow"))

    def _finish_turn(self) -> None:
        self._turn_active = False
        self._current_tool = None
        self._refresh_status()
        composer = self.query_one("#prompt", Composer)
        composer.focus()
        if self._queued and self.loop is not None:
            self._start_turn(self._queued.pop(0))

    # ---------- run events ----------

    def on_run_started(self, message: m.RunStarted) -> None:
        pass

    def on_model_activity(self, message: m.ModelActivity) -> None:
        self.query_one(StatusBar).set(est_tokens=message.estimated_tokens)

    def on_assistant_text(self, message: m.AssistantText) -> None:
        self._mount(AssistantMessage(message.text))

    def on_approval_requested(self, message: m.ApprovalRequested) -> None:
        tool = ToolActivity(message.tool, message.args)
        tool.set_awaiting()
        self._current_tool = tool
        self._mount(tool)

    def on_tool_started(self, message: m.ToolStarted) -> None:
        if self._current_tool is not None and self._current_tool.state == "awaiting":
            self._current_tool.set_running()
        else:
            tool = ToolActivity(message.name, message.args)
            tool.set_running()
            self._current_tool = tool
            self._mount(tool)
        self.query_one(StatusBar).set(state="working")

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
            self._mount(EventLine(f"⊘ {message.tool} denied: {message.reason}", "yellow"))

    def on_compacted(self, message: m.Compacted) -> None:
        self._mount(EventLine(f"↯ compacted history ({message.size} chars)"))

    def on_run_ended(self, message: m.RunEnded) -> None:
        if not message.completed:
            self._mount(EventLine(f"■ stopped: {message.status}", "yellow"))
        self._finish_turn()

    def on_run_failed(self, message: m.RunFailed) -> None:
        self._mount(EventLine(f"⚠ model error: {message.error}", "red"))
        self._mount(
            EventLine("The request failed — /login to update your key, or /model to switch.", "yellow")
        )
        self._finish_turn()
