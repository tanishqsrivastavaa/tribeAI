from __future__ import annotations

import json
import uuid
from pathlib import Path

from .messages import Message


class SessionStore:
    def __init__(self, root: str | Path = ".tribe/sessions"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self.root / f"{session_id}.jsonl"

    def create(self, session_id: str | None = None) -> str:
        session_id = session_id or uuid.uuid4().hex
        path = self._path(session_id)
        if path.exists():
            raise FileExistsError(f"session already exists: {session_id}")
        path.touch()
        return session_id

    def exists(self, session_id: str) -> bool:
        return self._path(session_id).exists()

    def append(self, session_id: str, message: Message) -> None:
        path = self._path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"unknown session: {session_id}")
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(message.to_dict(), ensure_ascii=False) + "\n")

    def load(self, session_id: str) -> list[Message]:
        path = self._path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"unknown session: {session_id}")
        messages = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    messages.append(Message.from_dict(json.loads(line)))
        return messages

    def list_sessions(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*.jsonl"))
