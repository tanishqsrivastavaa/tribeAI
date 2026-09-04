from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from .agent import AgentLoop
from .approvals import ApprovalGate, ApprovalPolicy
from .context import ContextBuilder
from .models import get_model, known_providers
from .observability import ConsoleObserver
from .sessions import SessionStore

SYSTEM_INSTRUCTIONS = (
    "You are Tribe, a minimal coding agent working inside a single workspace. "
    "Use the read, grep, write, and bash tools to inspect and change files and to "
    "run commands. Every path is relative to the workspace root. Prefer small, "
    "verified steps, and stop with a short summary once the task is done."
)

app = typer.Typer(help="Tribe, a minimal personal agent harness.", add_completion=False)

_PROVIDER_HELP = (
    f"Model provider: {', '.join(known_providers())} "
    "(default: anthropic; or use provider:model)."
)


def _format_args(args: dict) -> str:
    for key in ("path", "command", "pattern"):
        if key in args:
            return f"{key}={args[key]!r}"
    return str(args)


def _prompt_approval(tool: str, args: dict) -> bool:
    answer = input(f"Approve {tool} {_format_args(args)}? [y/N] ").strip().lower()
    return answer in ("y", "yes")


def build_loop(
    workspace: str,
    model: Optional[str],
    verbose: bool,
    yes: bool,
    provider: Optional[str] = None,
    context_limit: Optional[int] = None,
    model_factory=None,
) -> tuple[AgentLoop, SessionStore]:
    from .workspace import Workspace

    factory = model_factory or get_model
    store = SessionStore(Path(workspace) / ".tribe" / "sessions")
    gate = (
        ApprovalGate(ApprovalPolicy.auto_approve())
        if yes
        else ApprovalGate(ApprovalPolicy.default(), asker=_prompt_approval)
    )
    loop = AgentLoop(
        model=factory(model, provider=provider, context_limit=context_limit),
        workspace=Workspace(workspace),
        store=store,
        gate=gate,
        builder=ContextBuilder(instructions=SYSTEM_INSTRUCTIONS),
        observer=ConsoleObserver(verbose=verbose),
    )
    return loop, store


def _report(result, session_id: str) -> None:
    if result.final_text:
        typer.echo(result.final_text)
    if not result.completed:
        typer.echo(f"[stopped: {result.status} after {result.rounds} rounds]", err=True)
    typer.echo(f"session {session_id}", err=True)


def _interactive(loop: AgentLoop, session_id: str) -> None:
    typer.echo(f"session {session_id} — type 'exit' to quit", err=True)
    while True:
        try:
            line = input("» ")
        except EOFError:
            break
        if line.strip() in ("exit", "quit"):
            break
        if not line.strip():
            continue
        result = loop.run(session_id, line)
        if result.final_text:
            typer.echo(result.final_text)
        if not result.completed:
            typer.echo(f"[stopped: {result.status}]", err=True)


@app.command()
def run(
    prompt: str = typer.Argument(..., help="The task for the agent."),
    workspace: str = typer.Option(".", help="Workspace root the agent may act within."),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help=_PROVIDER_HELP),
    model: Optional[str] = typer.Option(None, help="Model id (default: provider default)."),
    context_limit: Optional[int] = typer.Option(
        None, "--context-limit", help="Override the model context window in tokens."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show a detailed run view."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve write and bash tools."),
) -> None:
    """Run a single task to completion."""
    loop, store = build_loop(
        workspace, model, verbose, yes, provider=provider, context_limit=context_limit
    )
    session_id = store.create()
    result = loop.run(session_id, prompt)
    _report(result, session_id)


@app.command()
def chat(
    workspace: str = typer.Option(".", help="Workspace root the agent may act within."),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help=_PROVIDER_HELP),
    model: Optional[str] = typer.Option(None, help="Model id (default: provider default)."),
    context_limit: Optional[int] = typer.Option(
        None, "--context-limit", help="Override the model context window in tokens."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show a detailed run view."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve write and bash tools."),
) -> None:
    """Start an interactive multi-turn session."""
    loop, store = build_loop(
        workspace, model, verbose, yes, provider=provider, context_limit=context_limit
    )
    _interactive(loop, store.create())


@app.command()
def resume(
    session_id: str = typer.Argument(..., help="Session id to resume."),
    prompt: Optional[str] = typer.Argument(None, help="Optional task; omit for interactive."),
    workspace: str = typer.Option(".", help="Workspace root the agent may act within."),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help=_PROVIDER_HELP),
    model: Optional[str] = typer.Option(None, help="Model id (default: provider default)."),
    context_limit: Optional[int] = typer.Option(
        None, "--context-limit", help="Override the model context window in tokens."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show a detailed run view."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve write and bash tools."),
) -> None:
    """Resume an existing session by id."""
    loop, store = build_loop(
        workspace, model, verbose, yes, provider=provider, context_limit=context_limit
    )
    if not store.exists(session_id):
        typer.echo(f"unknown session: {session_id}", err=True)
        raise typer.Exit(code=1)
    if prompt:
        result = loop.run(session_id, prompt)
        _report(result, session_id)
    else:
        _interactive(loop, session_id)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
