from __future__ import annotations

from typing import Callable

from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Input, RichLog, Static

from ..agent import AgentLoop
from ..agent.limits import Cancellation
from ..observability import Observer
from ..observability.console import _short
from ..sessions import SessionStore
from ..sessions.messages import Message, Role, ToolStatus
from . import messages as m
from .observer import TuiObserver
from .approval import TuiApprover

LoopFactory = Callable[[Observer, object], AgentLoop]


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
    ) -> None:
        super().__init__()
        self._loop_factory = loop_factory
        self.store = store
        self.session_id = session_id
        self.model_name = model_name
        self.loop: AgentLoop | None = None
        self.cancellation: Cancellation | None = None
        self._turn_active = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="transcript", wrap=True, markup=True)
        yield Static("", id="status")
        yield Input(placeholder="Message the agent…", id="prompt")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Tribe"
        self.loop = self._loop_factory(TuiObserver(self), TuiApprover(self))
        self.model_name = self.model_name or self.loop.model.name
        self.sub_title = f"{self.session_id[:8]} · {self.model_name}".strip(" ·")
        try:
            self.render_history(self.store.load(self.session_id))
        except FileNotFoundError:
            pass
        self.query_one("#prompt", Input).focus()

    @property
    def _transcript(self) -> RichLog:
        return self.query_one("#transcript", RichLog)

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

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
        self._start_turn(text)

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
