from __future__ import annotations

import os

from tribe import config
from tribe.agent import AgentLoop
from tribe.approvals import ApprovalGate, ApprovalPolicy
from tribe.models import ModelResponse, ScriptedModel
from tribe.sessions import SessionStore
from tribe.tui import TribeApp
from tribe.workspace import Workspace


async def test_login_saves_credentials(make_app):
    app, _, _ = make_app([ModelResponse(text="x")])
    async with app.run_test() as pilot:
        app._apply_login("groq", "gsk_secret", "llama-3.1-8b-instant")
        await pilot.pause()

    saved = config.load_config()
    assert saved["provider"] == "groq"
    assert saved["model"] == "llama-3.1-8b-instant"
    assert saved["keys"]["groq"] == "gsk_secret"


async def test_model_change_saves_model(make_app):
    app, _, _ = make_app([ModelResponse(text="x")])
    async with app.run_test() as pilot:
        app._on_model_only_chosen("claude-sonnet-5")
        await pilot.pause()

    saved = config.load_config()
    assert saved["provider"] == "anthropic"
    assert saved["model"] == "claude-sonnet-5"


async def test_startup_loads_stored_provider_key_and_model(tmp_path):
    config.save_config(
        {"provider": "groq", "model": "llama-x", "keys": {"groq": "gsk_stored"}}
    )
    provider, model = config.resolve_startup(None, None)
    assert os.environ["GROQ_API_KEY"] == "gsk_stored"

    store = SessionStore(tmp_path / ".tribe" / "sessions")
    session_id = store.create()
    calls = []

    def factory(observer, asker, provider=None, model=None):
        calls.append((provider, model))
        return AgentLoop(
            model=ScriptedModel([]),
            workspace=Workspace(tmp_path),
            store=store,
            gate=ApprovalGate(ApprovalPolicy.auto_approve()),
            observer=observer,
        )

    app = TribeApp(factory, store, session_id, provider=provider, model=model)
    async with app.run_test():
        assert app.provider == "groq"
        assert app.model == "llama-x"
        assert calls == [("groq", "llama-x")]
