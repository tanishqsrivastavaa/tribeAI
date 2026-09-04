from __future__ import annotations

import pytest
from typer.testing import CliRunner

from tribe import cli
from tribe.models import ModelResponse, ScriptedModel

runner = CliRunner()


@pytest.fixture
def spies(monkeypatch):
    calls = {"interactive": 0, "tui": 0}
    monkeypatch.setattr(cli, "get_model", lambda name=None, **kw: ScriptedModel([ModelResponse()]))
    monkeypatch.setattr(cli, "_interactive", lambda *a, **k: calls.__setitem__("interactive", calls["interactive"] + 1))

    import tribe.tui as tui

    monkeypatch.setattr(tui, "run_tui", lambda *a, **k: calls.__setitem__("tui", calls["tui"] + 1))
    return calls


def test_plain_flag_uses_repl(tmp_path, spies, monkeypatch):
    monkeypatch.setattr(cli, "_stdout_isatty", lambda: True)
    result = runner.invoke(cli.app, ["chat", "--workspace", str(tmp_path), "--plain"])
    assert result.exit_code == 0
    assert spies["interactive"] == 1
    assert spies["tui"] == 0


def test_non_tty_falls_back_to_repl(tmp_path, spies):
    # Under CliRunner stdout is not a tty.
    result = runner.invoke(cli.app, ["chat", "--workspace", str(tmp_path)])
    assert result.exit_code == 0
    assert spies["interactive"] == 1
    assert spies["tui"] == 0


def test_tty_launches_tui(tmp_path, spies, monkeypatch):
    monkeypatch.setattr(cli, "_stdout_isatty", lambda: True)
    result = runner.invoke(cli.app, ["chat", "--workspace", str(tmp_path)])
    assert result.exit_code == 0
    assert spies["tui"] == 1
    assert spies["interactive"] == 0
