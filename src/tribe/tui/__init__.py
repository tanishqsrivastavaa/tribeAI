from __future__ import annotations

from .app import TribeApp

__all__ = ["TribeApp", "run_tui"]


def run_tui(loop_factory, store, session_id: str, model_name: str = "") -> None:
    TribeApp(loop_factory, store, session_id, model_name).run()
