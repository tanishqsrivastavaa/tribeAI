from __future__ import annotations

from textual.widgets import Input

from tribe.agent import AgentLoop
from tribe.approvals import ApprovalGate, ApprovalPolicy
from tribe.models import ModelResponse, ScriptedModel
from tribe.sessions import SessionStore
from tribe.tui import TribeApp
from tribe.workspace import Workspace


async def test_no_credentials_stays_open_and_prompts_login(tmp_path, helpers):
    store = SessionStore(tmp_path / ".tribe" / "sessions")
    session_id = store.create()

    def factory(observer, asker, provider=None, model=None):
        return AgentLoop(
            model=ScriptedModel([ModelResponse(text="should never run")]),
            workspace=Workspace(tmp_path),
            store=store,
            gate=ApprovalGate(ApprovalPolicy.auto_approve()),
            observer=observer,
        )

    app = TribeApp(factory, store, session_id)  # provider None, no API key in env
    async with app.run_test() as pilot:
        assert app.loop is None
        lines = helpers.record_transcript(app)
        app.query_one("#prompt", Input).value = "hello"
        await pilot.press("enter")
        await pilot.pause()

    # the app is still alive (we exited run_test normally) and told the user to log in
    assert any("/login" in line for line in lines)
    assert not any("should never run" in line for line in lines)


async def test_model_error_keeps_app_open(make_app, helpers):
    def boom(_messages):
        raise RuntimeError("401 Unauthorized")

    app, _, _ = make_app([boom])
    async with app.run_test() as pilot:
        lines = helpers.record_transcript(app)
        app.query_one("#prompt", Input).value = "hi"
        await pilot.press("enter")
        await helpers.settle(pilot)
        assert not app._turn_active  # turn ended cleanly, app did not crash
        assert not app.query_one("#prompt", Input).disabled

    assert any("model error" in line for line in lines)
    assert any("401 Unauthorized" in line for line in lines)
    assert any("/login" in line for line in lines)


async def test_login_recovers_after_missing_credentials(tmp_path, helpers):
    store = SessionStore(tmp_path / ".tribe" / "sessions")
    session_id = store.create()

    def factory(observer, asker, provider=None, model=None):
        return AgentLoop(
            model=ScriptedModel([ModelResponse(text="now working")]),
            workspace=Workspace(tmp_path),
            store=store,
            gate=ApprovalGate(ApprovalPolicy.auto_approve()),
            observer=observer,
        )

    app = TribeApp(factory, store, session_id)
    async with app.run_test() as pilot:
        assert app.loop is None
        app._apply_login("groq", "gsk_test", "llama-3.1-8b-instant")
        await pilot.pause()
        assert app.loop is not None  # loop is built once credentials exist
        lines = helpers.record_transcript(app)
        app.query_one("#prompt", Input).value = "hi now"
        await pilot.press("enter")
        await helpers.settle(pilot)

    assert any("now working" in line for line in lines)
