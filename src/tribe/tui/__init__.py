from __future__ import annotations

from typing import Optional

from .app import TribeApp

__all__ = ["TribeApp", "run_tui"]


def run_tui(
    loop_factory,
    store,
    session_id: str,
    model_name: str = "",
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    TribeApp(loop_factory, store, session_id, model_name, provider, model).run()
