import io

from tribe.agent.limits import RunResult, RunStatus
from tribe.approvals import ApprovalMode
from tribe.observability import ConsoleObserver
from tribe.tools import ToolResult


def _observer(verbose=False):
    buf = io.StringIO()
    return ConsoleObserver(verbose=verbose, stream=buf), buf


def test_tool_start_always_shown():
    obs, buf = _observer(verbose=False)
    obs.tool_start("read", {"path": "a.txt"})
    assert "read" in buf.getvalue()
    assert "a.txt" in buf.getvalue()


def test_tool_error_shown_in_concise_mode():
    obs, buf = _observer(verbose=False)
    obs.tool_end("bash", ToolResult.fail("boom"), 0.01)
    assert "error: boom" in buf.getvalue()


def test_tool_success_hidden_in_concise_mode():
    obs, buf = _observer(verbose=False)
    obs.tool_end("read", ToolResult.ok("data"), 0.01)
    assert buf.getvalue() == ""


def test_tool_success_shown_in_verbose_mode():
    obs, buf = _observer(verbose=True)
    obs.tool_end("read", ToolResult.ok("data"), 0.05)
    assert "ok" in buf.getvalue()
    assert "ms" in buf.getvalue()


def test_verbose_approval_prints_mode_value():
    obs, buf = _observer(verbose=True)

    class Decision:
        allowed = True
        tool = "write"
        mode = ApprovalMode.ALLOW

    obs.approval(Decision())
    assert "allow" in buf.getvalue()
    assert "ApprovalMode" not in buf.getvalue()


def test_denied_approval_always_shown():
    obs, buf = _observer(verbose=False)

    class Decision:
        allowed = False
        tool = "bash"
        reason = "rejected by user"

    obs.approval(Decision())
    assert "denied" in buf.getvalue()


def test_model_request_verbose_only():
    quiet, qbuf = _observer(verbose=False)
    quiet.model_request(1234, 5)
    assert qbuf.getvalue() == ""

    loud, lbuf = _observer(verbose=True)
    loud.model_request(1234, 5)
    assert "1234" in lbuf.getvalue()


def test_run_end_reports_non_completion():
    obs, buf = _observer(verbose=False)
    obs.run_end(RunResult("s", RunStatus.MAX_ROUNDS, rounds=7))
    assert "stopped" in buf.getvalue()
    assert "max_rounds" in buf.getvalue()


def test_run_end_silent_on_completion_when_concise():
    obs, buf = _observer(verbose=False)
    obs.run_end(RunResult("s", RunStatus.COMPLETED, final_text="hi", rounds=2))
    assert buf.getvalue() == ""


def test_compaction_reported():
    obs, buf = _observer(verbose=False)

    class Summary:
        content = "x" * 42

    obs.compaction(Summary())
    assert "compacted" in buf.getvalue()
    assert "42" in buf.getvalue()
