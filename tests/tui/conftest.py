from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from tribe import cli
from tribe.models import ScriptedModel
from tribe.sessions import SessionStore
from tribe.tui import TribeApp
from tribe.tui.composer import Composer


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


class _LiveLines:
    """Live view over mounted transcript widgets; reads current text at iteration."""

    def __init__(self, widgets):
        self._widgets = widgets

    def __iter__(self):
        for widget in list(self._widgets):
            value = getattr(widget, "text_value", None)
            if value:
                yield value


def _record_transcript(app):
    """Capture transcript content by tracking widgets mounted into it."""
    captured = list(app._transcript.children)
    original = app._mount

    def mount(widget):
        captured.append(widget)
        return original(widget)

    app._mount = mount
    return _LiveLines(captured)


def _set_prompt(app, text):
    app.query_one("#prompt", Composer).value = text


async def _submit(pilot, text):
    pilot.app.query_one("#prompt", Composer).value = text
    await pilot.press("enter")


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
        set_prompt=_set_prompt,
        submit=_submit,
        settle=_settle,
        wait_until=_wait_until,
    )
