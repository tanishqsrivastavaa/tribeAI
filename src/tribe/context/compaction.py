from __future__ import annotations

import json

from ..models.base import Model
from ..sessions import messages as msg
from ..sessions.messages import Message, Role

SUMMARY_SYSTEM = (
    "You are compacting the history of a coding agent session so it can continue "
    "without the raw transcript. Write a dense summary that preserves:\n"
    "- The user's goal and constraints.\n"
    "- Decisions made and their rationale.\n"
    "- Important files, commands, outputs, and errors.\n"
    "- Work completed, work remaining, and current blockers.\n"
    "- Facts the agent must not rediscover or contradict.\n"
    "Do not invent information. Output only the summary."
)

_RESULT_CAP = 2000


def _render(message: Message) -> str:
    if message.role == Role.USER:
        return f"User: {message.content}"
    if message.role == Role.ASSISTANT:
        return f"Assistant: {message.content}"
    if message.role == Role.SUMMARY:
        return f"Earlier summary: {message.content}"
    if message.role == Role.TOOL_CALL:
        return f"Tool call {message.tool_name}({json.dumps(message.arguments or {})})"
    if message.role == Role.TOOL_RESULT:
        body = (message.result or "")[:_RESULT_CAP]
        status = message.status.value if message.status else "ok"
        return f"Tool result [{status}]: {body}"
    return message.content


def render_transcript(messages: list[Message]) -> str:
    return "\n".join(_render(m) for m in messages)


def compact(model: Model, history: list[Message], keep_recent: int) -> Message | None:
    if len(history) <= keep_recent:
        return None
    older = history[:-keep_recent]
    transcript = render_transcript(older)
    response = model.complete(
        SUMMARY_SYSTEM,
        [msg.user(f"Summarize this session so it can continue:\n\n{transcript}")],
        tools=None,
    )
    return msg.summary(response.text, older[0].id, older[-1].id)
