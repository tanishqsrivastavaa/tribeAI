from __future__ import annotations

import threading

from tribe.models import ModelResponse, ToolCall
from tribe.tui.widgets import ToolActivity


async def test_small_terminal_renders_a_turn(make_app, helpers):
    app, _, _ = make_app([ModelResponse(text="tiny screen reply")], yes=True)
    async with app.run_test(size=(40, 12)) as pilot:
        lines = helpers.record_transcript(app)
        await helpers.submit(pilot, "hi")
        await helpers.settle(pilot)
    assert any("tiny screen reply" in line for line in lines)


async def test_resize_during_active_turn(make_app, helpers):
    release = threading.Event()

    def blocking(_messages):
        release.wait(2)
        return ModelResponse(text="survived resize")

    app, _, _ = make_app([blocking])
    async with app.run_test(size=(100, 30)) as pilot:
        lines = helpers.record_transcript(app)
        await helpers.submit(pilot, "go")
        assert await helpers.wait_until(pilot, lambda: app._turn_active)
        await pilot.resize_terminal(50, 16)
        await pilot.resize_terminal(120, 40)
        release.set()
        await helpers.settle(pilot)
    assert any("survived resize" in line for line in lines)


async def test_rapid_tool_calls_all_render(make_app, helpers):
    calls = [ToolCall(f"c{i}", "read", {"path": "."}) for i in range(6)]
    app, _, _ = make_app(
        [ModelResponse(tool_calls=calls, stop_reason="tool_use"), ModelResponse(text="scanned")],
        yes=True,
    )
    async with app.run_test() as pilot:
        lines = helpers.record_transcript(app)
        await helpers.submit(pilot, "scan")
        await helpers.settle(pilot)
        tools = list(app.query(ToolActivity))
    assert len(tools) == 6
    assert all(t.state == "ok" for t in tools)
    assert any("scanned" in line for line in lines)


async def test_large_tool_output_is_clipped_but_retained(make_app, helpers):
    app, _, _ = make_app(
        [
            ModelResponse(
                tool_calls=[
                    ToolCall("c1", "bash", {"command": "python3 -c \"[print(i) for i in range(500)]\""})
                ],
                stop_reason="tool_use",
            ),
            ModelResponse(text="ran it"),
        ],
        yes=True,
    )
    async with app.run_test() as pilot:
        await helpers.submit(pilot, "print numbers")
        await helpers.settle(pilot)
        tool = app.query_one(ToolActivity)
        assert tool.state == "ok"
        # full output retained for inspection/session, display is clipped
        assert len(tool._output_text.splitlines()) == 500
        assert "more lines" in str(tool._output.render())


async def test_empty_session_starts_clean(make_app, helpers):
    app, _, _ = make_app([ModelResponse(text="x")])
    async with app.run_test() as pilot:
        await pilot.pause()
        # a brand new logged-in session shows no transcript items and does not crash
        assert app.transcript_text() == ""
