import pytest
from typer.testing import CliRunner

from tribe import cli
from tribe.models import ModelResponse, ScriptedModel, ToolCall

runner = CliRunner()


@pytest.fixture
def scripted(monkeypatch):
    holder = {}

    def install(steps):
        model = ScriptedModel(steps)
        holder["model"] = model
        holder["kwargs"] = []

        def factory(name=None, **kw):
            holder["kwargs"].append({"model": name, **kw})
            return model

        monkeypatch.setattr(cli, "get_model", factory)
        return holder

    return install


def test_run_prints_final_answer(tmp_path, scripted):
    scripted([ModelResponse(text="the answer")])
    result = runner.invoke(
        cli.app, ["run", "do a thing", "--workspace", str(tmp_path), "--yes"]
    )
    assert result.exit_code == 0
    assert "the answer" in result.stdout


def test_run_creates_session_file(tmp_path, scripted):
    scripted([ModelResponse(text="done")])
    runner.invoke(cli.app, ["run", "task", "--workspace", str(tmp_path), "--yes"])
    sessions = list((tmp_path / ".tribe" / "sessions").glob("*.jsonl"))
    assert len(sessions) == 1


def test_run_executes_tool(tmp_path, scripted):
    scripted(
        [
            ModelResponse(
                tool_calls=[ToolCall("c1", "write", {"path": "out.txt", "content": "hi"})],
                stop_reason="tool_use",
            ),
            ModelResponse(text="wrote it"),
        ]
    )
    result = runner.invoke(
        cli.app, ["run", "write out.txt", "--workspace", str(tmp_path), "--yes"]
    )
    assert result.exit_code == 0
    assert (tmp_path / "out.txt").read_text() == "hi"


def test_resume_unknown_session_errors(tmp_path, scripted):
    scripted([ModelResponse(text="x")])
    result = runner.invoke(
        cli.app, ["resume", "missing", "hello", "--workspace", str(tmp_path), "--yes"]
    )
    assert result.exit_code == 1
    assert "unknown session" in result.output


def test_resume_continues_existing_session(tmp_path, scripted):
    scripted([ModelResponse(text="first"), ModelResponse(text="second")])
    runner.invoke(cli.app, ["run", "start", "--workspace", str(tmp_path), "--yes"])
    sessions = list((tmp_path / ".tribe" / "sessions").glob("*.jsonl"))
    sid = sessions[0].stem

    result = runner.invoke(
        cli.app, ["resume", sid, "again", "--workspace", str(tmp_path), "--yes"]
    )
    assert result.exit_code == 0
    assert "second" in result.stdout


def test_build_loop_wires_workspace(tmp_path):
    loop, store = cli.build_loop(
        str(tmp_path),
        model=None,
        verbose=False,
        yes=True,
        model_factory=lambda name=None, **kw: ScriptedModel([]),
    )
    assert loop.workspace.root == tmp_path.resolve()
    assert "read" in loop.registry


def test_help_lists_commands():
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0
    for command in ("run", "chat", "resume"):
        assert command in result.stdout


def test_run_forwards_provider_and_model(tmp_path, scripted):
    holder = scripted([ModelResponse(text="ok")])
    result = runner.invoke(
        cli.app,
        [
            "run", "task",
            "--workspace", str(tmp_path),
            "--provider", "groq",
            "--model", "llama-3.1-8b-instant",
            "--yes",
        ],
    )
    assert result.exit_code == 0
    assert holder["kwargs"][0]["provider"] == "groq"
    assert holder["kwargs"][0]["model"] == "llama-3.1-8b-instant"


def test_run_forwards_context_limit(tmp_path, scripted):
    holder = scripted([ModelResponse(text="ok")])
    runner.invoke(
        cli.app,
        ["run", "task", "--workspace", str(tmp_path), "--context-limit", "32000", "--yes"],
    )
    assert holder["kwargs"][0]["context_limit"] == 32000


def test_run_help_lists_providers():
    result = runner.invoke(cli.app, ["run", "--help"])
    assert result.exit_code == 0
    output = result.stdout
    assert "groq" in output and "openrouter" in output
