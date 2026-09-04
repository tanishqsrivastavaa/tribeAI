from __future__ import annotations

from typing import Any

from ..sessions.messages import Message, Role, ToolStatus
from .base import Model, ModelResponse, ToolCall, Usage
from .registry import context_limit_for


def to_anthropic(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    i, n = 0, len(messages)
    while i < n:
        m = messages[i]
        if m.role == Role.SYSTEM:
            i += 1
        elif m.role == Role.USER:
            out.append({"role": "user", "content": m.content})
            i += 1
        elif m.role == Role.SUMMARY:
            out.append(
                {"role": "user", "content": f"[Summary of earlier conversation]\n{m.content}"}
            )
            i += 1
        elif m.role in (Role.ASSISTANT, Role.TOOL_CALL):
            content: list[dict[str, Any]] = []
            if m.role == Role.ASSISTANT:
                if m.content:
                    content.append({"type": "text", "text": m.content})
                i += 1
            while i < n and messages[i].role == Role.TOOL_CALL:
                tc = messages[i]
                content.append(
                    {
                        "type": "tool_use",
                        "id": tc.call_id,
                        "name": tc.tool_name,
                        "input": tc.arguments or {},
                    }
                )
                i += 1
            if not content:
                content = [{"type": "text", "text": ""}]
            out.append({"role": "assistant", "content": content})
        elif m.role == Role.TOOL_RESULT:
            content = []
            while i < n and messages[i].role == Role.TOOL_RESULT:
                tr = messages[i]
                content.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tr.call_id,
                        "content": tr.result or "",
                        "is_error": tr.status == ToolStatus.ERROR,
                    }
                )
                i += 1
            out.append({"role": "user", "content": content})
        else:
            i += 1
    return out


class AnthropicModel(Model):
    def __init__(
        self,
        name: str,
        client: Any = None,
        max_tokens: int = 16000,
        context_limit: int | None = None,
    ):
        self.name = name
        self.context_limit = context_limit or context_limit_for(name)
        self.max_tokens = max_tokens
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client = client

    def complete(self, system, messages, tools=None):
        request: dict[str, Any] = {
            "model": self.name,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": to_anthropic(messages),
        }
        if tools:
            request["tools"] = tools

        response = self.client.messages.create(**request)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(block.id, block.name, dict(block.input)))

        usage = Usage(
            getattr(response.usage, "input_tokens", 0),
            getattr(response.usage, "output_tokens", 0),
        )
        return ModelResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=response.stop_reason,
            usage=usage,
        )
