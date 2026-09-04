from __future__ import annotations

import os
from typing import Callable, Optional

from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Input, RichLog, Static

from ..agent import AgentLoop
from ..agent.limits import Cancellation
from ..models import DEFAULT_PROVIDER, PROVIDERS
from ..observability import Observer
from ..observability.console import _short
from ..sessions import SessionStore
from ..sessions.messages import Message, Role, ToolStatus
from . import messages as m
from .approval import TuiApprover
from .login import ApiKeyScreen, ModelSelectScreen, ProviderSelectScreen
from .observer import TuiObserver
from .screens import SessionsScreen

LoopFactory = Callable[[Observer, object, Optional[str], Optional[str]], AgentLoop]


class TribeApp(App):
    CSS = """
    #transcript { height: 1fr; padding: 0 1; }
    #status { height: 1; color: $text-muted; padding: 0 1; }
    #approval-box {
        width: 60%;
        height: auto;
        padding: 1 2;
        border: thick $primary;
        background: $surface;
    }
    ApprovalModal { align: center middle; }
    #approval-title { padding-bottom: 1; }
    #approval-args { color: $text-muted; padding-bottom: 1; }
    ProviderSelectScreen, ApiKeyScreen, ModelSelectScreen { align: center middle; }
    #login-box {
        width: 70%;
        height: auto;
        padding: 1 2;
        border: thick $primary;
        background: $surface;
    }
    #login-title { text-style: bold; padding-bottom: 1; }
    #login-hint { color: $text-muted; padding-bottom: 1; }
    #login-error { color: $error; }
    #provider-list { height: auto; max-height: 15; }
    #sessions-list { height: auto; max-height: 15; }
    """

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+c", "cancel", "Cancel turn"),
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
        self._observer: Observer | None = None
        self._approver: TuiApprover | None = None
        self._pending_provider: str | None = None
        self._pending_key: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="transcript", wrap=True, markup=True)
        yield Static("", id="status")
        yield Input(placeholder="Message the agent…  (/help for commands)", id="prompt")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Tribe"
        self._observer = TuiObserver(self)
        self._approver = TuiApprover(self)
        try:
            self.render_history(self.store.load(self.session_id))
        except FileNotFoundError:
            pass
        self._build_loop(initial=True)
        self.query_one("#prompt", Input).focus()

    @property
    def _transcript(self) -> RichLog:
        return self.query_one("#transcript", RichLog)

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def _update_subtitle(self) -> None:
        state = self.model_name if self.loop is not None else "not logged in"
        self.sub_title = f"{self.session_id[:8]} · {state}".strip(" ·")

    def _build_loop(self, initial: bool = False) -> bool:
        try:
            self.loop = self._loop_factory(
                self._observer, self._approver, self.provider, self.model
            )
        except Exception as exc:  # noqa: BLE001
            self.loop = None
            if initial:
                self._transcript.write(
                    "[yellow]No model configured. Type [b]/login[/b] to choose a "
                    "provider and add an API key.[/]"
                )
            else:
                self._transcript.write(f"[red]could not initialize model: {exc}[/]")
            self._update_subtitle()
            return False
        self.model_name = self.loop.model.name
        if self.provider is None:
            self.provider = DEFAULT_PROVIDER
        self._update_subtitle()
        return True

    def render_history(self, history: list[Message]) -> None:
        for msg in history:
            if msg.role == Role.USER:
                self._transcript.write(f"[b cyan]you[/]  {msg.content}")
            elif msg.role == Role.ASSISTANT and msg.content:
                self._transcript.write(f"[b green]tribe[/]  {msg.content}")
            elif msg.role == Role.TOOL_CALL:
                self._transcript.write(f"[dim]⚙ {msg.tool_name} {_short(msg.arguments or {})}[/]")
            elif msg.role == Role.TOOL_RESULT and msg.status == ToolStatus.ERROR:
                self._transcript.write(f"[red]  ↳ error: {msg.error}[/]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or self._turn_active:
            return
        event.input.value = ""
        if text.startswith("/"):
            self._handle_command(text)
            return
        if self.loop is None:
            self._transcript.write(
                "[yellow]No model configured. Type [b]/login[/b] first.[/]"
            )
            return
        self._start_turn(text)

    def _handle_command(self, text: str) -> None:
        command = text[1:].split()[0].lower()
        if command == "login":
            self._start_login()
        elif command == "model":
            self._start_model_change()
        elif command == "sessions":
            self._start_sessions()
        elif command == "help":
            self._transcript.write(
                "[dim]commands: /login (provider + key + model), "
                "/model (switch model), /sessions (open a past session), /help[/]"
            )
        else:
            self._transcript.write(f"[yellow]unknown command: /{command}[/]")

    def _start_login(self) -> None:
        self.push_screen(ProviderSelectScreen(), self._on_provider_chosen)

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
            self._transcript.write(
                f"[b green]✓ logged in[/]  provider [b]{provider}[/] · "
                f"model [b]{self.model_name}[/]"
            )
        self.query_one("#prompt", Input).focus()

    def _start_model_change(self) -> None:
        if not self.provider:
            self._transcript.write("[yellow]No provider yet. Type [b]/login[/b] first.[/]")
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
            self._transcript.write(f"[b green]✓ model set[/]  [b]{self.model_name}[/]")
        self.query_one("#prompt", Input).focus()

    def _start_sessions(self) -> None:
        if not self.store.list_sessions():
            self._transcript.write("[yellow]no saved sessions[/]")
            return
        self.push_screen(SessionsScreen(self.store, self.session_id), self._on_session_chosen)

    def _on_session_chosen(self, session_id: str | None) -> None:
        if not session_id or session_id == self.session_id:
            return
        self.session_id = session_id
        self._transcript.clear()
        try:
            self.render_history(self.store.load(session_id))
        except FileNotFoundError:
            pass
        self._update_subtitle()
        self.query_one("#prompt", Input).focus()

    def _start_turn(self, text: str) -> None:
        self._turn_active = True
        self.cancellation = Cancellation()
        self._transcript.write(f"[b cyan]you[/]  {text}")
        self._set_status("working…")
        inp = self.query_one("#prompt", Input)
        inp.disabled = True
        self._run_turn(text)

    @work(thread=True)
    def _run_turn(self, text: str) -> None:
        assert self.loop is not None
        self.loop.run(self.session_id, text, self.cancellation)

    def action_cancel(self) -> None:
        if self._turn_active and self.cancellation is not None:
            self.cancellation.cancel()
            self._set_status("cancelling…")

    def _finish_turn(self) -> None:
        self._turn_active = False
        self._set_status("")
        inp = self.query_one("#prompt", Input)
        inp.disabled = False
        inp.focus()

    def on_run_started(self, message: m.RunStarted) -> None:
        pass

    def on_model_activity(self, message: m.ModelActivity) -> None:
        self._set_status(f"thinking… (~{message.estimated_tokens} tok)")

    def on_tool_started(self, message: m.ToolStarted) -> None:
        self._transcript.write(f"[dim]⚙ {message.name} {_short(message.args)}[/]")
        self._set_status(f"running {message.name}…")

    def on_tool_ended(self, message: m.ToolEnded) -> None:
        if message.is_error:
            self._transcript.write(f"[red]  ↳ error: {message.error}[/]")

    def on_approval_resolved(self, message: m.ApprovalResolved) -> None:
        if not message.allowed:
            self._transcript.write(f"[yellow]⛔ {message.tool} denied: {message.reason}[/]")

    def on_compacted(self, message: m.Compacted) -> None:
        self._transcript.write(f"[dim]↯ compacted history ({message.size} chars)[/]")

    def on_run_ended(self, message: m.RunEnded) -> None:
        if message.final_text:
            self._transcript.write(f"[b green]tribe[/]  {message.final_text}")
        if not message.completed:
            self._transcript.write(f"[yellow]■ stopped: {message.status}[/]")
        self._finish_turn()
