from __future__ import annotations

from textual.widgets import Input

from tribe.models import ModelResponse, ToolCall
from tribe.sessions.messages import Role
from tribe.tui.screens import ApprovalModal


async def _submit(pilot, text):
    pilot.app.query_one("#prompt", Input).value = text
    await pilot.press("enter")


async def test_basic_turn_renders_reply_and_persists(make_app, helpers):
    app, store, session_id = make_app([ModelResponse(text="hello there")])
    async with app.run_test() as pilot:
        lines = helpers.record_transcript(app)
        await _submit(pilot, "hi")
        await helpers.settle(pilot)

    assert any("hi" in line for line in lines)
    assert any("hello there" in line for line in lines)

    roles = [(m.role, m.content) for m in store.load(session_id)]
    assert (Role.USER, "hi") in roles
    assert (Role.ASSISTANT, "hello there") in roles


async def test_tool_activity_runs_and_renders(make_app, helpers, tmp_path):
    app, store, session_id = make_app(
        [
            ModelResponse(
                tool_calls=[ToolCall("c1", "write", {"path": "out.txt", "content": "hi"})],
                stop_reason="tool_use",
            ),
            ModelResponse(text="wrote it"),
        ],
        yes=True,
    )
    async with app.run_test() as pilot:
        lines = helpers.record_transcript(app)
        await _submit(pilot, "make the file")
        await helpers.settle(pilot)

    assert (tmp_path / "out.txt").read_text() == "hi"
    assert any("write" in line for line in lines)


async def test_approval_modal_approve_runs_tool(make_app, helpers, tmp_path):
    app, store, session_id = make_app(
        [
            ModelResponse(
                tool_calls=[ToolCall("c1", "write", {"path": "ok.txt", "content": "x"})],
                stop_reason="tool_use",
            ),
            ModelResponse(text="done"),
        ],
        yes=False,
    )
    async with app.run_test() as pilot:
        await _submit(pilot, "write ok.txt")
        assert await helpers.wait_until(pilot, lambda: isinstance(app.screen, ApprovalModal))
        await pilot.press("y")
        await helpers.settle(pilot)

    assert (tmp_path / "ok.txt").read_text() == "x"


async def test_approval_modal_deny_blocks_tool(make_app, helpers, tmp_path):
    app, store, session_id = make_app(
        [
            ModelResponse(
                tool_calls=[ToolCall("c1", "write", {"path": "no.txt", "content": "x"})],
                stop_reason="tool_use",
            ),
            ModelResponse(text="stopped"),
        ],
        yes=False,
    )
    async with app.run_test() as pilot:
        lines = helpers.record_transcript(app)
        await _submit(pilot, "write no.txt")
        assert await helpers.wait_until(pilot, lambda: isinstance(app.screen, ApprovalModal))
        await pilot.press("n")
        await helpers.settle(pilot)

    assert not (tmp_path / "no.txt").exists()
    assert any("denied" in line for line in lines)
    results = [m for m in store.load(session_id) if m.role == Role.TOOL_RESULT]
    assert results and "approval denied" in (results[0].result or "")


async def test_cancel_stops_run(make_app, helpers):
    def cancel_mid_run(_messages):
        app.cancellation.cancel()
        return ModelResponse(
            tool_calls=[ToolCall("c1", "read", {"path": "x"})], stop_reason="tool_use"
        )

    app, store, session_id = make_app([cancel_mid_run, ModelResponse(text="unreached")])
    async with app.run_test() as pilot:
        lines = helpers.record_transcript(app)
        await _submit(pilot, "go")
        await helpers.settle(pilot)

    assert any("cancelled" in line for line in lines)


async def test_action_cancel_sets_flag(make_app):
    from tribe.agent.limits import Cancellation

    app, store, session_id = make_app([ModelResponse(text="x")])
    async with app.run_test() as pilot:
        app._turn_active = True
        app.cancellation = Cancellation()
        app.action_cancel()
        assert app.cancellation.cancelled
