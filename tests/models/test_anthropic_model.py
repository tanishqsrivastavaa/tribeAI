from types import SimpleNamespace

from tribe.models.anthropic_model import AnthropicModel
from tribe.sessions import messages


class FakeMessages:
    def __init__(self, response):
        self._response = response
        self.last_request = None

    def create(self, **kwargs):
        self.last_request = kwargs
        return self._response


class FakeClient:
    def __init__(self, response):
        self.messages = FakeMessages(response)


def _response(blocks, stop_reason="end_turn", in_tok=10, out_tok=5):
    return SimpleNamespace(
        content=blocks,
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok),
    )


def test_parses_text_response():
    resp = _response([SimpleNamespace(type="text", text="hello")])
    model = AnthropicModel("claude-opus-4-8", client=FakeClient(resp))
    result = model.complete("sys", [messages.user("hi")])
    assert result.text == "hello"
    assert not result.wants_tools
    assert result.usage.input_tokens == 10


def test_parses_tool_use_response():
    resp = _response(
        [
            SimpleNamespace(type="text", text="reading"),
            SimpleNamespace(
                type="tool_use", id="c1", name="read", input={"path": "a.txt"}
            ),
        ],
        stop_reason="tool_use",
    )
    model = AnthropicModel("claude-opus-4-8", client=FakeClient(resp))
    result = model.complete("sys", [messages.user("read a")], tools=[{"name": "read"}])
    assert result.wants_tools
    assert result.tool_calls[0].name == "read"
    assert result.tool_calls[0].arguments == {"path": "a.txt"}
    assert result.stop_reason == "tool_use"


def test_request_includes_model_and_tools():
    resp = _response([SimpleNamespace(type="text", text="x")])
    client = FakeClient(resp)
    model = AnthropicModel("claude-opus-4-8", client=client, max_tokens=1234)
    model.complete("system prompt", [messages.user("hi")], tools=[{"name": "read"}])
    req = client.messages.last_request
    assert req["model"] == "claude-opus-4-8"
    assert req["max_tokens"] == 1234
    assert req["system"] == "system prompt"
    assert req["tools"] == [{"name": "read"}]


def test_no_tools_key_when_none():
    resp = _response([SimpleNamespace(type="text", text="x")])
    client = FakeClient(resp)
    AnthropicModel("claude-opus-4-8", client=client).complete("s", [messages.user("hi")])
    assert "tools" not in client.messages.last_request


def test_context_limit_set_from_registry():
    model = AnthropicModel("claude-haiku-4-5", client=FakeClient(_response([])))
    assert model.context_limit == 200_000
