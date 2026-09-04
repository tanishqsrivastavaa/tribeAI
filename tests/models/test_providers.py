import pytest

from tribe.models import get_model
from tribe.models.anthropic_model import AnthropicModel
from tribe.models.openai_model import OpenAIModel
from tribe.models.providers import known_providers, resolve_provider


def test_default_provider_is_anthropic():
    spec, model = resolve_provider(None, None)
    assert spec.name == "anthropic"
    assert model == "claude-opus-4-8"


def test_explicit_provider_uses_its_default_model():
    spec, model = resolve_provider(None, "groq")
    assert spec.backend == "openai"
    assert spec.base_url == "https://api.groq.com/openai/v1"
    assert model == "llama-3.3-70b-versatile"


def test_provider_colon_model_prefix():
    spec, model = resolve_provider("groq:llama-3.1-8b-instant", None)
    assert spec.name == "groq"
    assert model == "llama-3.1-8b-instant"


def test_colon_in_model_without_known_prefix_is_untouched():
    spec, model = resolve_provider("meta-llama/llama-3.1-8b-instruct:free", "openrouter")
    assert spec.name == "openrouter"
    assert model == "meta-llama/llama-3.1-8b-instruct:free"


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="unknown provider"):
        resolve_provider(None, "nope")


def test_known_providers_include_majors():
    providers = known_providers()
    for name in ("anthropic", "openai", "openrouter", "groq"):
        assert name in providers


def test_get_model_dispatches_to_openai_backend():
    model = get_model(provider="openrouter", client=object())
    assert isinstance(model, OpenAIModel)
    assert model.name == "openai/gpt-4o"


def test_get_model_dispatches_to_anthropic_backend():
    model = get_model(provider="anthropic", client=object())
    assert isinstance(model, AnthropicModel)


def test_get_model_forwards_context_limit():
    model = get_model(provider="groq", client=object(), context_limit=32_000)
    assert model.context_limit == 32_000


def test_get_model_missing_key_reports_env_var(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        get_model(provider="groq")
