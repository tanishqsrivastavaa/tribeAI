from __future__ import annotations

DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_CONTEXT_LIMIT = 200_000

CONTEXT_LIMITS = {
    "claude-fable-5-1": 1_000_000,
    "claude-fable-5": 1_000_000,
    "claude-opus-5": 1_000_000,
    "claude-opus-4-8": 1_000_000,
    "claude-opus-4-7": 1_000_000,
    "claude-opus-4-6": 1_000_000,
    "claude-sonnet-5": 1_000_000,
    "claude-sonnet-4-6": 1_000_000,
    "claude-haiku-4-5": 200_000,
}


def context_limit_for(model: str) -> int:
    return CONTEXT_LIMITS.get(model, DEFAULT_CONTEXT_LIMIT)


def get_model(model: str | None = None, **kwargs):
    from .anthropic_model import AnthropicModel

    return AnthropicModel(model or DEFAULT_MODEL, **kwargs)
