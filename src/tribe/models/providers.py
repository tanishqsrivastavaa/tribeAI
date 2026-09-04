from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PROVIDER = "anthropic"


@dataclass(frozen=True)
class Provider:
    name: str
    backend: str  # "anthropic" or "openai"
    default_model: str
    base_url: str | None = None
    api_key_env: str | None = None


PROVIDERS: dict[str, Provider] = {
    "anthropic": Provider(
        "anthropic", "anthropic", "claude-opus-4-8", api_key_env="ANTHROPIC_API_KEY"
    ),
    "openai": Provider(
        "openai", "openai", "gpt-4o", api_key_env="OPENAI_API_KEY"
    ),
    "openrouter": Provider(
        "openrouter",
        "openai",
        "openai/gpt-4o",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
    ),
    "groq": Provider(
        "groq",
        "openai",
        "llama-3.3-70b-versatile",
        base_url="https://api.groq.com/openai/v1",
        api_key_env="GROQ_API_KEY",
    ),
    "deepseek": Provider(
        "deepseek",
        "openai",
        "deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key_env="DEEPSEEK_API_KEY",
    ),
    "together": Provider(
        "together",
        "openai",
        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        base_url="https://api.together.xyz/v1",
        api_key_env="TOGETHER_API_KEY",
    ),
    "fireworks": Provider(
        "fireworks",
        "openai",
        "accounts/fireworks/models/llama-v3p3-70b-instruct",
        base_url="https://api.fireworks.ai/inference/v1",
        api_key_env="FIREWORKS_API_KEY",
    ),
    "xai": Provider(
        "xai",
        "openai",
        "grok-2-latest",
        base_url="https://api.x.ai/v1",
        api_key_env="XAI_API_KEY",
    ),
}


def known_providers() -> list[str]:
    return sorted(PROVIDERS)


def resolve_provider(
    model: str | None, provider: str | None
) -> tuple[Provider, str]:
    if provider is None and model and ":" in model:
        prefix, rest = model.split(":", 1)
        if prefix in PROVIDERS:
            provider, model = prefix, rest

    provider = provider or DEFAULT_PROVIDER
    spec = PROVIDERS.get(provider)
    if spec is None:
        raise ValueError(
            f"unknown provider: {provider!r} (known: {', '.join(known_providers())})"
        )
    return spec, model or spec.default_model
