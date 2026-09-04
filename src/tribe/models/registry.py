from __future__ import annotations

DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_CONTEXT_LIMIT = 128_000

CONTEXT_LIMITS = {
    # Anthropic
    "claude-fable-5-1": 1_000_000,
    "claude-fable-5": 1_000_000,
    "claude-opus-5": 1_000_000,
    "claude-opus-4-8": 1_000_000,
    "claude-opus-4-7": 1_000_000,
    "claude-opus-4-6": 1_000_000,
    "claude-sonnet-5": 1_000_000,
    "claude-sonnet-4-6": 1_000_000,
    "claude-haiku-4-5": 200_000,
    # OpenAI
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4.1": 1_000_000,
    "gpt-4.1-mini": 1_000_000,
    "o3": 200_000,
    "o4-mini": 200_000,
    # Groq
    "llama-3.3-70b-versatile": 128_000,
    "llama-3.1-8b-instant": 128_000,
    # DeepSeek
    "deepseek-chat": 64_000,
    "deepseek-reasoner": 64_000,
}


def context_limit_for(model: str) -> int:
    return CONTEXT_LIMITS.get(model, DEFAULT_CONTEXT_LIMIT)


def get_model(
    model: str | None = None,
    provider: str | None = None,
    context_limit: int | None = None,
    **kwargs,
):
    from .providers import resolve_provider

    spec, model = resolve_provider(model, provider)
    limit = context_limit or context_limit_for(model)

    if spec.backend == "anthropic":
        from .anthropic_model import AnthropicModel

        return AnthropicModel(model, context_limit=limit, **kwargs)

    from .openai_model import OpenAIModel

    return OpenAIModel(
        model,
        base_url=spec.base_url,
        api_key_env=spec.api_key_env,
        context_limit=limit,
        **kwargs,
    )
