from tribe.tools.bash import BashTool


def test_bash_captures_stdout(ctx):
    result = BashTool().invoke({"command": "echo hello"}, ctx)
    assert not result.is_error
    assert "hello" in result.output
    assert result.metadata["exit_code"] == 0


def test_bash_nonzero_exit_is_error(ctx):
    result = BashTool().invoke({"command": "exit 3"}, ctx)
    assert result.is_error
    assert result.metadata["exit_code"] == 3


def test_bash_runs_in_workspace(ctx):
    (ctx.workspace.root / "marker.txt").write_text("x")
    result = BashTool().invoke({"command": "ls"}, ctx)
    assert "marker.txt" in result.output


def test_bash_timeout(ctx):
    ctx.timeout = 0.2
    result = BashTool().invoke({"command": "sleep 2"}, ctx)
    assert result.is_error
    assert "timed out" in result.error
