from __future__ import annotations

import pytest
from textual.widgets import Input

from tribe.models import ModelResponse
from tribe.sessions import SessionStore
from tribe.sessions import messages as smsg
from tribe.sessions.messages import Role
from tribe.tui import TribeApp
from tribe.tui.login import ModelSelectScreen
from tribe.tui.screens import SessionsScreen


# ---------- /model ----------

async def test_model_command_opens_screen_when_provider_set(make_app, helpers):
    app, _, _ = make_app([ModelResponse(text="x")])
    async with app.run_test() as pilot:
        assert app.provider == "anthropic"  # effective provider after a default build
        app.query_one("#prompt", Input).value = "/model"
        await pilot.press("enter")
        assert await helpers.wait_until(
            pilot, lambda: isinstance(app.screen, ModelSelectScreen)
        )


async def test_model_change_rebuilds_with_new_model(make_app, helpers):
    app, _, _ = make_app([ModelResponse(text="x")])
    async with app.run_test() as pilot:
        app.query_one("#prompt", Input).value = "/model"
        await pilot.press("enter")
        assert await helpers.wait_until(
            pilot, lambda: isinstance(app.screen, ModelSelectScreen)
        )
        model_input = app.screen.query_one("#model-input", Input)
        model_input.focus()
        model_input.value = "claude-sonnet-5"
        await pilot.press("enter")
        await helpers.settle(pilot)

    assert app.model == "claude-sonnet-5"
    assert {"provider": "anthropic", "model": "claude-sonnet-5"} in app.factory_calls


async def test_model_command_without_provider_hints_login(tmp_path, helpers):
    def raising_factory(observer, asker, provider=None, model=None):
        raise RuntimeError("no key")

    store = SessionStore(tmp_path / ".tribe" / "sessions")
    session_id = store.create()
    app = TribeApp(raising_factory, store, session_id)
    async with app.run_test() as pilot:
        assert app.provider is None
        lines = helpers.record_transcript(app)
        app.query_one("#prompt", Input).value = "/model"
        await pilot.press("enter")
        await pilot.pause()

    assert any("/login" in line for line in lines)


async def test_model_cancel_leaves_model_unchanged(make_app, helpers):
    app, _, _ = make_app([ModelResponse(text="x")])
    async with app.run_test() as pilot:
        before = app.model
        app.query_one("#prompt", Input).value = "/model"
        await pilot.press("enter")
        assert await helpers.wait_until(
            pilot, lambda: isinstance(app.screen, ModelSelectScreen)
        )
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, ModelSelectScreen)
    assert app.model == before


# ---------- /sessions ----------

async def test_sessions_command_opens_picker(make_app, helpers):
    app, _, _ = make_app([ModelResponse(text="x")])
    async with app.run_test() as pilot:
        app.query_one("#prompt", Input).value = "/sessions"
        await pilot.press("enter")
        assert await helpers.wait_until(pilot, lambda: isinstance(app.screen, SessionsScreen))


async def test_sessions_switch_loads_history_and_targets_new_session(make_app, helpers):
    app, store, current_id = make_app([ModelResponse(text="switched reply")])
    store.create("other")
    store.append("other", smsg.user("hello old session"))

    async with app.run_test() as pilot:
        lines = helpers.record_transcript(app)
        app.query_one("#prompt", Input).value = "/sessions"
        await pilot.press("enter")
        assert await helpers.wait_until(pilot, lambda: isinstance(app.screen, SessionsScreen))
        await pilot.press("enter")  # most recent (the non-empty "other")
        await helpers.settle(pilot)

        assert app.session_id == "other"
        assert any("hello old session" in line for line in lines)

        # a new turn now targets the switched session
        app.query_one("#prompt", Input).value = "hi again"
        await pilot.press("enter")
        await helpers.settle(pilot)

    contents = [(msg.role, msg.content) for msg in store.load("other")]
    assert (Role.USER, "hi again") in contents
    assert (Role.ASSISTANT, "switched reply") in contents


async def test_sessions_cancel_keeps_current(make_app, helpers):
    app, _, current_id = make_app([ModelResponse(text="x")])
    async with app.run_test() as pilot:
        app.query_one("#prompt", Input).value = "/sessions"
        await pilot.press("enter")
        assert await helpers.wait_until(pilot, lambda: isinstance(app.screen, SessionsScreen))
        await pilot.press("escape")
        await pilot.pause()
    assert app.session_id == current_id


async def test_help_lists_new_commands(make_app, helpers):
    app, _, _ = make_app([ModelResponse(text="x")])
    async with app.run_test() as pilot:
        lines = helpers.record_transcript(app)
        app.query_one("#prompt", Input).value = "/help"
        await pilot.press("enter")
        await pilot.pause()
    assert any("/model" in line and "/sessions" in line for line in lines)
