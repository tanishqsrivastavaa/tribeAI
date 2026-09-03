from __future__ import annotations

import json

from ..sessions.messages import Message

CHARS_PER_TOKEN = 4
PER_MESSAGE_OVERHEAD = 4


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def _message_chars(message: Message) -> int:
    total = len(message.content or "")
    if message.arguments:
        total += len(json.dumps(message.arguments))
    if message.result:
        total += len(message.result)
    if message.error:
        total += len(message.error)
    return total


def estimate_message(message: Message) -> int:
    return estimate_tokens("x" * _message_chars(message)) + PER_MESSAGE_OVERHEAD


def estimate_messages(messages: list[Message]) -> int:
    return sum(estimate_message(m) for m in messages)
