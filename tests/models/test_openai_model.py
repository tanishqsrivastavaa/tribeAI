import json
from types import SimpleNamespace

from tribe.models.openai_model import OpenAIModel
from tribe.sessions import messages


class FakeCompletions:
    def __init__(self, response):
        self._response = response
        self.last_request = None

    def create(self, **kwargs):
        self.last_request = kwargs
        return self._response


class FakeClient:
    def __init__(self, response):
        self.chat = SimpleNamespace(completions=FakeCompletions(response))


def _response(content=None, tool_calls=None, finish_reason="stop", pt=7, ct=3):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    usage = SimpleNamespace(prompt_tokens=pt, completion_tokens=ct)
    return SimpleNamespace(choices=[choice], usage=usage)


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def test_parses_text_response():
    model = OpenAIModel("gpt-4o", client=FakeClient(_response(content="hi there")))
    result = model.complete("sys", [messages.user("hello")])
    assert result.text == "hi there"
    assert not result.wants_tools
    assert result.usage.input_tokens == 7
    assert result.usage.output_tokens == 3


def test_parses_tool_calls_with_json_arguments():
    resp = _response(
        tool_calls=[_tool_call("c1", "read", {"path": "a.txt"})],
        finish_reason="tool_calls",
    )
    model = OpenAIModel("gpt-4o", client=FakeClient(resp))
    result = model.complete("sys", [messages.user("read")], tools=[])
    assert result.wants_tools
    assert result.tool_calls[0].name == "read"
    assert result.tool_calls[0].arguments == {"path": "a.txt"}
    assert result.stop_reason == "tool_calls"


def test_malformed_tool_arguments_default_to_empty():
    bad = SimpleNamespace(id="c1", function=SimpleNamespace(name="x", arguments="{not json"))
    model = OpenAIModel("gpt-4o", client=FakeClient(_response(tool_calls=[bad])))
    result = model.complete("s", [messages.user("go")])
    assert result.tool_calls[0].arguments == {}


def test_request_prepends_system_and_converts_tools():
    client = FakeClient(_response(content="ok"))
    model = OpenAIModel("gpt-4o", client=client, max_tokens=999)
    model.complete(
        "system prompt",
        [messages.user("hi")],
        tools=[{"name": "read", "description": "d", "input_schema": {"type": "object"}}],
    )
    req = client.chat.completions.last_request
    assert req["model"] == "gpt-4o"
    assert req["max_tokens"] == 999
    assert req["messages"][0] == {"role": "system", "content": "system prompt"}
    assert req["tools"][0]["type"] == "function"
    assert req["tools"][0]["function"]["name"] == "read"
    assert req["tools"][0]["function"]["parameters"] == {"type": "object"}


def test_no_tools_key_when_none():
    client = FakeClient(_response(content="x"))
    OpenAIModel("gpt-4o", client=client).complete("s", [messages.user("hi")])
    assert "tools" not in client.chat.completions.last_request


def test_missing_api_key_raises_clear_error():
    import pytest

    with pytest.raises(RuntimeError, match="MISSING_KEY_ENV"):
        OpenAIModel("gpt-4o", api_key_env="MISSING_KEY_ENV")


def test_context_limit_from_registry():
    model = OpenAIModel("gpt-4o", client=FakeClient(_response(content="x")))
    assert model.context_limit == 128_000
