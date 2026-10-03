from __future__ import annotations

import threading
import time

from textual.widgets import Input, OptionList

from tribe.models import ModelResponse, ToolCall
from tribe.sessions import messages as smsg
from tribe.sessions.messages import Role
from tribe.tui.screens import ApprovalModal, SessionsScreen


async def test_multiple_assistant_narrations_render(make_app, helpers):
    app, _, _ = make_app(
        [
            ModelResponse(
                text="Let me look first.",
                tool_calls=[ToolCall("c1", "read", {"path": "."})],
                stop_reason="tool_use",
            ),
            ModelResponse(text="All done."),
        ],
        yes=True,
    )
    async with app.run_test() as pilot:
        lines = helpers.record_transcript(app)
        await helpers.submit(pilot, "go")
        await helpers.settle(pilot)
    assert any("Let me look first." in line for line in lines)
    assert any("All done." in line for line in lines)
    assert any("read ." in line for line in lines)


async def test_input_stays_enabled_and_queues_follow_up(make_app, helpers):
    release = threading.Event()

    def blocking(_messages):
        release.wait(2)
        return ModelResponse(text="first reply")

    app, store, session_id = make_app([blocking, ModelResponse(text="second reply")])
    async with app.run_test() as pilot:
        lines = helpers.record_transcript(app)
        await helpers.submit(pilot, "first")
        assert await helpers.wait_until(pilot, lambda: app._turn_active)
        # composer is never disabled during a turn
        from tribe.tui.composer import Composer

        assert not app.query_one("#prompt", Composer).disabled
        await helpers.submit(pilot, "second")
        assert app._queued == ["second"]
        assert any("queued" in line for line in lines)
        release.set()
        assert await helpers.wait_until(
            pilot, lambda: not app._turn_active and not app._queued, tries=100
        )

    contents = [(m.role, m.content) for m in store.load(session_id)]
    assert (Role.USER, "first") in contents
    assert (Role.USER, "second") in contents
    assert any("first reply" in line for line in lines)
    assert any("second reply" in line for line in lines)


async def test_interrupt_then_redirect(make_app, helpers):
    release = threading.Event()

    def blocking(_messages):
        for _ in range(200):
            if app.cancellation and app.cancellation.cancelled:
                break
            time.sleep(0.01)
        release.wait(2)
        return ModelResponse(
            tool_calls=[ToolCall("c1", "read", {"path": "x"})], stop_reason="tool_use"
        )

    app, store, session_id = make_app([blocking, ModelResponse(text="redirected reply")])
    async with app.run_test() as pilot:
        lines = helpers.record_transcript(app)
        await helpers.submit(pilot, "original")
        assert await helpers.wait_until(pilot, lambda: app._turn_active)
        app.action_cancel()
        assert app.cancellation.cancelled
        await helpers.submit(pilot, "go this way instead")
        assert app._queued == ["go this way instead"]
        release.set()
        assert await helpers.wait_until(
            pilot, lambda: not app._turn_active and not app._queued, tries=100
        )

    contents = [(m.role, m.content) for m in store.load(session_id)]
    assert (Role.USER, "go this way instead") in contents
    assert any("redirected reply" in line for line in lines)
    assert any("interrupting" in line for line in lines)


async def test_always_allow_skips_second_approval(make_app, helpers, tmp_path):
    app, _, _ = make_app(
        [
            ModelResponse(
                tool_calls=[ToolCall("c1", "write", {"path": "a.txt", "content": "1"})],
                stop_reason="tool_use",
            ),
            ModelResponse(
                tool_calls=[ToolCall("c2", "write", {"path": "b.txt", "content": "2"})],
                stop_reason="tool_use",
            ),
            ModelResponse(text="done"),
        ],
        yes=False,
    )
    async with app.run_test() as pilot:
        await helpers.submit(pilot, "write both")
        assert await helpers.wait_until(pilot, lambda: isinstance(app.screen, ApprovalModal))
        await pilot.press("a")  # always allow write for this session
        # the second write must proceed without another modal
        assert await helpers.wait_until(
            pilot, lambda: (tmp_path / "b.txt").exists(), tries=100
        )
        assert not isinstance(app.screen, ApprovalModal)

    assert (tmp_path / "a.txt").read_text() == "1"
    assert (tmp_path / "b.txt").read_text() == "2"


async def test_sessions_search_filters_and_opens(make_app, helpers):
    app, store, _ = make_app([ModelResponse(text="x")])
    store.create("alpha")
    store.append("alpha", smsg.user("apple pie recipe"))
    store.create("beta")
    store.append("beta", smsg.user("banana bread notes"))

    async with app.run_test() as pilot:
        await helpers.submit(pilot, "/sessions")
        assert await helpers.wait_until(pilot, lambda: isinstance(app.screen, SessionsScreen))
        screen = app.screen
        screen.query_one("#session-filter", Input).focus()
        await pilot.press(*"banana")
        await pilot.pause()
        option_list = screen.query_one(OptionList)
        assert option_list.option_count == 1
        await pilot.press("enter")
        await helpers.settle(pilot)

    assert app.session_id == "beta"


async def test_escape_interrupts_active_turn_without_leaving_prompt(make_app, helpers):
    from tribe.tui.composer import Composer

    release = threading.Event()

    def blocking(_messages):
        release.wait(2)
        return ModelResponse(text="late")

    app, _, _ = make_app([blocking])
    async with app.run_test() as pilot:
        await helpers.submit(pilot, "go")
        assert await helpers.wait_until(pilot, lambda: app._turn_active)
        await pilot.press("escape")
        assert app.cancellation.cancelled
        assert app.focused is app.query_one("#prompt", Composer)
        release.set()
        await helpers.settle(pilot)


async def test_escape_closes_command_menu(make_app, helpers):
    app, _, _ = make_app([ModelResponse(text="x")])
    async with app.run_test() as pilot:
        await pilot.press("/")
        await pilot.pause()
        assert app._menu is not None and app._menu.display
        await pilot.press("escape")
        await pilot.pause()
        assert not app._menu.display


async def test_activity_line_tracks_turn(make_app, helpers):
    from tribe.tui.widgets import ActivityLine

    release = threading.Event()

    def blocking(_messages):
        release.wait(2)
        return ModelResponse(text="reply")

    app, _, _ = make_app([blocking])
    async with app.run_test() as pilot:
        lines = helpers.record_transcript(app)
        activity = app.query_one(ActivityLine)
        await helpers.submit(pilot, "go")
        assert await helpers.wait_until(pilot, lambda: app._turn_active)
        assert activity.label == "Thinking"
        assert "esc to interrupt" in activity.hint
        release.set()
        await helpers.settle(pilot)
        assert activity.label == "" and activity.hint == ""
    assert any(line.startswith("◆ done in") for line in lines)


async def test_tool_run_updates_activity_label(make_app, helpers):
    from tribe.tui.widgets import ActivityLine

    labels = []
    app, _, _ = make_app(
        [
            ModelResponse(
                tool_calls=[ToolCall("c1", "read", {"path": "."})], stop_reason="tool_use"
            ),
            ModelResponse(text="ok"),
        ]
    )
    async with app.run_test() as pilot:
        activity = app.query_one(ActivityLine)
        original = activity.start
        activity.start = lambda label: (labels.append(label), original(label))
        await helpers.submit(pilot, "go")
        await helpers.settle(pilot)
    assert "Running read" in labels


async def test_short_transcript_stays_top_aligned(make_app, helpers):
    app, _, _ = make_app([ModelResponse(text="short")])
    async with app.run_test(size=(100, 40)) as pilot:
        await helpers.submit(pilot, "hi")
        await helpers.settle(pilot)
        await pilot.pause()
        transcript = app._transcript
        assert transcript.max_scroll_y == 0
        assert transcript.scroll_y == 0
        assert not transcript.is_anchored


async def test_long_reply_follows_to_bottom(make_app, helpers):
    long_reply = "\n\n".join(f"paragraph {i}" for i in range(60))
    app, _, _ = make_app([ModelResponse(text=long_reply)])
    async with app.run_test(size=(80, 24)) as pilot:
        await helpers.submit(pilot, "hi")
        await helpers.settle(pilot)
        transcript = app._transcript
        assert await helpers.wait_until(
            pilot, lambda: transcript.max_scroll_y > 0 and transcript.scroll_y == transcript.max_scroll_y
        )
        assert transcript.is_anchored


async def test_approval_choices_work_from_keyboard(make_app, helpers, tmp_path):
    app, _, _ = make_app(
        [
            ModelResponse(
                tool_calls=[ToolCall("c1", "write", {"path": "a.txt", "content": "1"})],
                stop_reason="tool_use",
            ),
            ModelResponse(
                tool_calls=[ToolCall("c2", "write", {"path": "b.txt", "content": "2"})],
                stop_reason="tool_use",
            ),
            ModelResponse(text="done"),
        ],
        yes=False,
    )
    async with app.run_test() as pilot:
        await helpers.submit(pilot, "write both")
        assert await helpers.wait_until(pilot, lambda: isinstance(app.screen, ApprovalModal))
        await pilot.press("enter")  # first choice: yes
        assert await helpers.wait_until(pilot, lambda: (tmp_path / "a.txt").exists(), tries=100)
        assert await helpers.wait_until(pilot, lambda: isinstance(app.screen, ApprovalModal))
        await pilot.press("down", "down", "enter")  # last choice: no
        await helpers.settle(pilot)

    assert (tmp_path / "a.txt").read_text() == "1"
    assert not (tmp_path / "b.txt").exists()
