from __future__ import annotations

import os

from textual.widgets import Input

from tribe.models import ModelResponse
from tribe.sessions import SessionStore
from tribe.tui import TribeApp
from tribe.tui.login import ApiKeyScreen, ModelSelectScreen, ProviderSelectScreen


async def _login_cmd(app, pilot):
    app.query_one("#prompt", Input).value = "/login"
    await pilot.press("enter")


async def test_login_command_opens_provider_menu(make_app, helpers):
    app, _, _ = make_app([ModelResponse(text="x")])
    async with app.run_test() as pilot:
        await _login_cmd(app, pilot)
        assert await helpers.wait_until(
            pilot, lambda: isinstance(app.screen, ProviderSelectScreen)
        )


async def test_full_login_flow_returns_to_tui(make_app, helpers):
    app, _, _ = make_app([ModelResponse(text="x")])
    async with app.run_test() as pilot:
        await _login_cmd(app, pilot)
        assert await helpers.wait_until(
            pilot, lambda: isinstance(app.screen, ProviderSelectScreen)
        )
        await pilot.press("enter")  # first option (anthropic)

        assert await helpers.wait_until(pilot, lambda: isinstance(app.screen, ApiKeyScreen))
        key_input = app.screen.query_one("#key-input", Input)
        key_input.focus()
        key_input.value = "sk-test-123"
        await pilot.press("enter")

        assert await helpers.wait_until(
            pilot, lambda: isinstance(app.screen, ModelSelectScreen)
        )
        app.screen.query_one("#model-input", Input).focus()
        await pilot.press("enter")  # accept default model
        await helpers.settle(pilot)

    assert app.provider == "anthropic"
    assert app.model == "claude-opus-4-8"
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-test-123"
    assert {"provider": "anthropic", "model": "claude-opus-4-8"} in app.factory_calls


async def test_apply_login_sets_provider_key_and_rebuilds(make_app, helpers):
    app, _, _ = make_app([ModelResponse(text="x")])
    async with app.run_test() as pilot:
        app._apply_login("groq", "gsk_secret", "llama-3.1-8b-instant")
        await pilot.pause()

    assert os.environ["GROQ_API_KEY"] == "gsk_secret"
    assert app.provider == "groq"
    assert app.model == "llama-3.1-8b-instant"
    assert {"provider": "groq", "model": "llama-3.1-8b-instant"} in app.factory_calls


async def test_cancel_at_provider_menu_changes_nothing(make_app, helpers):
    app, _, _ = make_app([ModelResponse(text="x")])
    async with app.run_test() as pilot:
        before = app.provider
        await _login_cmd(app, pilot)
        assert await helpers.wait_until(
            pilot, lambda: isinstance(app.screen, ProviderSelectScreen)
        )
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, ProviderSelectScreen)
    assert app.provider == before


async def test_help_and_unknown_command(make_app, helpers):
    app, _, _ = make_app([ModelResponse(text="x")])
    async with app.run_test() as pilot:
        lines = helpers.record_transcript(app)
        app.query_one("#prompt", Input).value = "/help"
        await pilot.press("enter")
        await pilot.pause()
        app.query_one("#prompt", Input).value = "/bogus"
        await pilot.press("enter")
        await pilot.pause()

    assert any("commands:" in line for line in lines)
    assert any("unknown command" in line for line in lines)


async def test_startup_without_credentials_prompts_login(tmp_path, helpers):
    def raising_factory(observer, asker, provider=None, model=None):
        raise RuntimeError("GROQ_API_KEY is not set")

    store = SessionStore(tmp_path / ".tribe" / "sessions")
    session_id = store.create()
    app = TribeApp(raising_factory, store, session_id)

    async with app.run_test() as pilot:
        assert app.loop is None
        lines = helpers.record_transcript(app)
        app.query_one("#prompt", Input).value = "hello"
        await pilot.press("enter")
        await pilot.pause()

    assert any("/login" in line for line in lines)


async def test_subtitle_shows_not_logged_in_when_no_loop(tmp_path):
    def raising_factory(observer, asker, provider=None, model=None):
        raise RuntimeError("no key")

    store = SessionStore(tmp_path / ".tribe" / "sessions")
    session_id = store.create()
    app = TribeApp(raising_factory, store, session_id)
    async with app.run_test():
        assert "not logged in" in app.sub_title
