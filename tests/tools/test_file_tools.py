from tribe.tools.read import ReadTool
from tribe.tools.write import WriteTool
from tribe.tools.grep import GrepTool


def test_read_file(ctx):
    (ctx.workspace.root / "a.txt").write_text("hello")
    result = ReadTool().invoke({"path": "a.txt"}, ctx)
    assert not result.is_error
    assert result.output == "hello"


def test_read_directory_lists_entries(ctx):
    (ctx.workspace.root / "sub").mkdir()
    (ctx.workspace.root / "a.txt").write_text("x")
    result = ReadTool().invoke({"path": "."}, ctx)
    assert "sub/" in result.output
    assert "a.txt" in result.output


def test_read_missing_file_errors(ctx):
    result = ReadTool().invoke({"path": "nope.txt"}, ctx)
    assert result.is_error


def test_read_rejects_escape(ctx):
    result = ReadTool().invoke({"path": "../escape.txt"}, ctx)
    assert result.is_error


def test_write_creates_file_and_parents(ctx):
    result = WriteTool().invoke({"path": "nested/dir/f.txt", "content": "data"}, ctx)
    assert not result.is_error
    assert (ctx.workspace.root / "nested" / "dir" / "f.txt").read_text() == "data"


def test_write_overwrites(ctx):
    (ctx.workspace.root / "f.txt").write_text("old")
    WriteTool().invoke({"path": "f.txt", "content": "new"}, ctx)
    assert (ctx.workspace.root / "f.txt").read_text() == "new"


def test_write_rejects_escape(ctx):
    result = WriteTool().invoke({"path": "../evil.txt", "content": "x"}, ctx)
    assert result.is_error


def test_grep_finds_matches(ctx):
    (ctx.workspace.root / "a.py").write_text("def foo():\n    return 1\n")
    (ctx.workspace.root / "b.py").write_text("x = 2\n")
    result = GrepTool().invoke({"pattern": r"def \w+"}, ctx)
    assert "a.py:1:def foo():" in result.output
    assert result.metadata["count"] == 1


def test_grep_no_matches(ctx):
    (ctx.workspace.root / "a.txt").write_text("nothing here")
    result = GrepTool().invoke({"pattern": "zzz"}, ctx)
    assert not result.is_error
    assert result.metadata["count"] == 0


def test_grep_invalid_pattern_errors(ctx):
    result = GrepTool().invoke({"pattern": "("}, ctx)
    assert result.is_error
