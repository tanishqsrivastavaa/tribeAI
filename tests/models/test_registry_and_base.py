from tribe.models import ModelResponse, ToolCall, Usage, context_limit_for
from tribe.models.registry import DEFAULT_CONTEXT_LIMIT, DEFAULT_MODEL


def test_context_limit_known_model():
    assert context_limit_for("claude-haiku-4-5") == 200_000
    assert context_limit_for("claude-opus-4-8") == 1_000_000


def test_context_limit_unknown_model_falls_back():
    assert context_limit_for("some-future-model") == DEFAULT_CONTEXT_LIMIT


def test_default_model_is_known():
    assert context_limit_for(DEFAULT_MODEL) > 0


def test_response_wants_tools():
    assert not ModelResponse(text="hi").wants_tools
    assert ModelResponse(tool_calls=[ToolCall("1", "read", {})]).wants_tools


def test_usage_defaults():
    u = Usage()
    assert u.input_tokens == 0 and u.output_tokens == 0
