import os

import pytest

from tribe.workspace import Workspace, WorkspaceError


def test_resolves_relative_path_inside_root(tmp_path):
    ws = Workspace(tmp_path)
    (tmp_path / "a.txt").write_text("hi")
    assert ws.resolve("a.txt") == tmp_path / "a.txt"


def test_resolves_nested_path(tmp_path):
    ws = Workspace(tmp_path)
    (tmp_path / "sub").mkdir()
    assert ws.resolve("sub/b.txt") == tmp_path / "sub" / "b.txt"


def test_allows_nonexistent_path_for_writing(tmp_path):
    ws = Workspace(tmp_path)
    assert ws.resolve("new/file.txt") == tmp_path / "new" / "file.txt"


def test_rejects_parent_traversal(tmp_path):
    ws = Workspace(tmp_path)
    with pytest.raises(WorkspaceError):
        ws.resolve("../secret.txt")


def test_rejects_absolute_path_outside(tmp_path):
    ws = Workspace(tmp_path)
    with pytest.raises(WorkspaceError):
        ws.resolve("/etc/passwd")


def test_rejects_symlink_escape(tmp_path):
    outside = tmp_path.parent / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    root = tmp_path / "ws"
    root.mkdir()
    os.symlink(outside, root / "link")

    ws = Workspace(root)
    with pytest.raises(WorkspaceError):
        ws.resolve("link/secret.txt")


def test_allows_symlink_within_workspace(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    (root / "real").mkdir()
    (root / "real" / "f.txt").write_text("ok")
    os.symlink(root / "real", root / "alias")

    ws = Workspace(root)
    assert ws.resolve("alias/f.txt") == root / "real" / "f.txt"


def test_contains(tmp_path):
    ws = Workspace(tmp_path)
    assert ws.contains("inside.txt")
    assert not ws.contains("../outside.txt")


def test_root_must_be_directory(tmp_path):
    f = tmp_path / "file"
    f.write_text("x")
    with pytest.raises(WorkspaceError):
        Workspace(f)
