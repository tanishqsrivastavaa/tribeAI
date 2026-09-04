from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from textual.widgets import RichLog

from tribe import cli
from tribe.models import ScriptedModel
from tribe.sessions import SessionStore
from tribe.tui import TribeApp


@pytest.fixture
def make_app(tmp_path):
    def build(steps, yes=True):
        os.environ["ANTHROPIC_API_KEY"] = "test-key"  # represent a logged-in session
        store = SessionStore(tmp_path / ".tribe" / "sessions")
        session_id = store.create()
        model = ScriptedModel(steps)
        calls: list[dict] = []

        def loop_factory(observer, asker, provider=None, model_name=None):
            calls.append({"provider": provider, "model": model_name})
            loop, _ = cli.build_loop(
                str(tmp_path),
                model=None,
                verbose=False,
                yes=yes,
                model_factory=lambda name=None, **kw: model,
                store=store,
                observer=observer,
                asker=asker,
            )
            return loop

        app = TribeApp(loop_factory, store, session_id)
        app.factory_calls = calls
        return app, store, session_id

    return build


def _record_transcript(app):
    """Wrap the transcript's write to capture rendered lines as plain text."""
    log = app.query_one(RichLog)
    lines: list[str] = []
    original = log.write

    def write(content, *args, **kwargs):
        lines.append(str(content))
        return original(content, *args, **kwargs)

    log.write = write
    return lines


async def _settle(pilot):
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def _wait_until(pilot, predicate, tries=50):
    for _ in range(tries):
        if predicate():
            return True
        await pilot.pause()
    return predicate()


@pytest.fixture
def helpers():
    return SimpleNamespace(
        record_transcript=_record_transcript,
        settle=_settle,
        wait_until=_wait_until,
    )
