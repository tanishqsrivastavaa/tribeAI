from __future__ import annotations

import time
from typing import Any

from ..approvals import ApprovalGate, ApprovalPolicy
from ..context import ContextBuilder, compact
from ..models.base import Model, ToolCall
from ..observability import NullObserver, Observer
from ..sessions import SessionStore
from ..sessions import messages as msg
from ..sessions.messages import Message, ToolStatus
from ..tools import ToolContext, ToolResult, ToolValidationError, default_tools
from ..workspace import Workspace
from .limits import Cancellation, RunLimits, RunResult, RunStatus


class AgentLoop:
    def __init__(
        self,
        model: Model,
        workspace: Workspace,
        tools=None,
        store: SessionStore | None = None,
        builder: ContextBuilder | None = None,
        gate: ApprovalGate | None = None,
        limits: RunLimits | None = None,
        observer: Observer | None = None,
    ):
        self.model = model
        self.workspace = workspace
        self.tools = tools or default_tools()
        self.registry = {t.name: t for t in self.tools}
        self.specs = [t.spec() for t in self.tools]
        self.store = store or SessionStore()
        self.builder = builder or ContextBuilder()
        self.gate = gate or ApprovalGate(ApprovalPolicy.default())
        self.limits = limits or RunLimits()
        self.observer = observer or NullObserver()

    def run(
        self, session_id: str, user_input: str, cancellation: Cancellation | None = None
    ) -> RunResult:
        self.store.append(session_id, msg.user(user_input))
        self.observer.run_start(session_id, user_input)
        ctx = ToolContext(self.workspace, timeout=self.limits.tool_timeout)
        consecutive_failures = 0
        rounds = 0

        while True:
            if cancellation and cancellation.cancelled:
                return self._end(session_id, RunStatus.CANCELLED, rounds)
            if rounds >= self.limits.max_rounds:
                return self._end(session_id, RunStatus.MAX_ROUNDS, rounds)

            self._maybe_compact(session_id)
            system, history = self.builder.build(self.store.load(session_id))
            self.observer.model_request(self.builder.estimate(history), len(history))
            response = self.model.complete(system, history, self.specs)
            self.observer.model_response(response)
            rounds += 1

            if not response.wants_tools:
                if response.text:
                    self.store.append(session_id, msg.assistant(response.text))
                return self._end(session_id, RunStatus.COMPLETED, rounds, response.text)

            self.store.append(session_id, msg.assistant(response.text))
            for call in response.tool_calls:
                self.store.append(
                    session_id, msg.tool_call(call.name, call.id, call.arguments)
                )

            for call in response.tool_calls:
                if cancellation and cancellation.cancelled:
                    return self._end(session_id, RunStatus.CANCELLED, rounds)
                result_msg, failed = self._execute(call, ctx)
                self.store.append(session_id, result_msg)
                if failed:
                    consecutive_failures += 1
                    if consecutive_failures >= self.limits.max_consecutive_failures:
                        return self._end(
                            session_id, RunStatus.MAX_CONSECUTIVE_FAILURES, rounds
                        )
                else:
                    consecutive_failures = 0

    def _maybe_compact(self, session_id: str) -> None:
        messages = self.store.load(session_id)
        if not self.builder.should_compact(messages, self.model.context_limit):
            return
        history = self.builder.effective_history(messages)
        summary = compact(self.model, history, self.builder.keep_recent)
        if summary is not None:
            self.store.append(session_id, summary)
            self.observer.compaction(summary)

    def _execute(self, call: ToolCall, ctx: ToolContext) -> tuple[Message, bool]:
        decision = self.gate.check(call.name, call.arguments)
        self.observer.approval(decision)
        if not decision.allowed:
            content = f"approval denied: {decision.reason}"
            return (
                msg.tool_result(call.name, call.id, content, ToolStatus.ERROR, decision.reason),
                False,
            )

        tool = self.registry.get(call.name)
        if tool is None:
            content = f"unknown tool: {call.name}"
            return msg.tool_result(call.name, call.id, content, ToolStatus.ERROR, content), True

        self.observer.tool_start(call.name, call.arguments)
        start = time.monotonic()
        try:
            result = tool.invoke(call.arguments, ctx)
        except ToolValidationError as exc:
            result = ToolResult.fail(str(exc))
        except Exception as exc:  # noqa: BLE001
            result = ToolResult.fail(f"{type(exc).__name__}: {exc}")
        duration = time.monotonic() - start
        self.observer.tool_end(call.name, result, duration)

        if result.is_error:
            content = result.error or ""
            if result.output:
                content += ("\n" if content else "") + result.output
            return (
                msg.tool_result(call.name, call.id, content, ToolStatus.ERROR, result.error),
                True,
            )
        return msg.tool_result(call.name, call.id, result.output, ToolStatus.OK), False

    def _end(
        self,
        session_id: str,
        status: str,
        rounds: int,
        final_text: Any = None,
    ) -> RunResult:
        result = RunResult(session_id, status, final_text, rounds)
        self.observer.run_end(result)
        return result
