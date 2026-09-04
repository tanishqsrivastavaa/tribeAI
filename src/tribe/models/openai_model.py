from __future__ import annotations

import json
import os
from typing import Any

from ..sessions.messages import Message, Role
from .base import Model, ModelResponse, ToolCall, Usage
from .registry import context_limit_for


def to_openai(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    i, n = 0, len(messages)
    while i < n:
        m = messages[i]
        if m.role == Role.SYSTEM:
            out.append({"role": "system", "content": m.content})
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
            text = ""
            if m.role == Role.ASSISTANT:
                text = m.content
                i += 1
            tool_calls = []
            while i < n and messages[i].role == Role.TOOL_CALL:
                tc = messages[i]
                tool_calls.append(
                    {
                        "id": tc.call_id,
                        "type": "function",
                        "function": {
                            "name": tc.tool_name,
                            "arguments": json.dumps(tc.arguments or {}),
                        },
                    }
                )
                i += 1
            entry: dict[str, Any] = {"role": "assistant", "content": text or None}
            if tool_calls:
                entry["tool_calls"] = tool_calls
            elif entry["content"] is None:
                entry["content"] = ""
            out.append(entry)
        elif m.role == Role.TOOL_RESULT:
            out.append(
                {"role": "tool", "tool_call_id": m.call_id, "content": m.result or ""}
            )
            i += 1
        else:
            i += 1
    return out


def _to_function_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


class OpenAIModel(Model):
    """Backend for OpenAI and any OpenAI-compatible provider (OpenRouter, Groq, ...)."""

    def __init__(
        self,
        name: str,
        client: Any = None,
        base_url: str | None = None,
        api_key_env: str | None = None,
        api_key: str | None = None,
        context_limit: int | None = None,
        max_tokens: int = 16000,
    ):
        self.name = name
        self.context_limit = context_limit or context_limit_for(name)
        self.max_tokens = max_tokens
        if client is None:
            import openai

            key = api_key or (os.environ.get(api_key_env) if api_key_env else None)
            if api_key_env and not key:
                raise RuntimeError(f"{api_key_env} is not set")
            options: dict[str, Any] = {"api_key": key}
            if base_url:
                options["base_url"] = base_url
            client = openai.OpenAI(**options)
        self.client = client

    def complete(self, system, messages, tools=None):
        convo = to_openai(messages)
        if system:
            convo = [{"role": "system", "content": system}] + convo

        request: dict[str, Any] = {
            "model": self.name,
            "messages": convo,
            "max_tokens": self.max_tokens,
        }
        if tools:
            request["tools"] = _to_function_tools(tools)

        response = self.client.chat.completions.create(**request)
        choice = response.choices[0]
        message = choice.message

        tool_calls: list[ToolCall] = []
        for call in getattr(message, "tool_calls", None) or []:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except (json.JSONDecodeError, TypeError):
                arguments = {}
            tool_calls.append(ToolCall(call.id, call.function.name, arguments))

        usage = Usage(
            getattr(response.usage, "prompt_tokens", 0),
            getattr(response.usage, "completion_tokens", 0),
        )
        return ModelResponse(
            text=message.content or "",
            tool_calls=tool_calls,
            stop_reason=choice.finish_reason or "stop",
            usage=usage,
        )
