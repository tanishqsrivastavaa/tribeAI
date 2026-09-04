from __future__ import annotations

from dataclasses import dataclass

from tribe.agent.limits import RunResult, RunStatus
from tribe.approvals import ApprovalDecision
from tribe.sessions import messages as smsg
from tribe.tui import messages as m
from tribe.tui.observer import TuiObserver


class FakeApp:
    def __init__(self):
        self.posted = []

    def post_message(self, message):
        self.posted.append(message)


@dataclass
class FakeResult:
    is_error: bool
    error: str | None = None
    output: str = ""


def test_observer_translates_events_to_messages():
    app = FakeApp()
    obs = TuiObserver(app)

    obs.run_start("sid", "hello")
    obs.model_request(123, 4)
    obs.tool_start("write", {"path": "a.txt"})
    obs.tool_end("write", FakeResult(is_error=False), 0.01)
    obs.tool_end("bash", FakeResult(is_error=True, error="boom"), 0.02)
    obs.approval(ApprovalDecision("bash", False, "ask", "rejected by user"))
    obs.compaction(smsg.summary("abc", "s", "e"))
    obs.run_end(RunResult("sid", RunStatus.COMPLETED, "final", 3))

    kinds = [type(x) for x in app.posted]
    assert kinds == [
        m.RunStarted,
        m.ModelActivity,
        m.ToolStarted,
        m.ToolEnded,
        m.ToolEnded,
        m.ApprovalResolved,
        m.Compacted,
        m.RunEnded,
    ]

    assert app.posted[1].estimated_tokens == 123
    assert app.posted[4].is_error and app.posted[4].error == "boom"
    assert app.posted[5].allowed is False
    assert app.posted[6].size == 3
    ended = app.posted[7]
    assert ended.final_text == "final" and ended.completed is True
