from __future__ import annotations

import os
from pathlib import Path


class WorkspaceError(Exception):
    pass


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(os.path.realpath(root))
        if not self.root.is_dir():
            raise WorkspaceError(f"workspace root is not a directory: {self.root}")

    def resolve(self, path: str) -> Path:
        target = os.path.realpath(os.path.join(self.root, path))
        root = str(self.root)
        if target != root and not target.startswith(root + os.sep):
            raise WorkspaceError(f"path escapes workspace: {path}")
        return Path(target)

    def contains(self, path: str) -> bool:
        try:
            self.resolve(path)
            return True
        except WorkspaceError:
            return False


__all__ = ["Workspace", "WorkspaceError"]
