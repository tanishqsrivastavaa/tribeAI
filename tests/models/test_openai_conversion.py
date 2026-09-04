import json

from tribe.models.openai_model import to_openai
from tribe.sessions import messages


def test_user_and_assistant():
    conv = to_openai([messages.user("hi"), messages.assistant("hello")])
    assert conv == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


def test_system_message_kept_as_system_role():
    conv = to_openai([messages.system("rules")])
    assert conv == [{"role": "system", "content": "rules"}]


def test_summary_becomes_user_context():
    conv = to_openai([messages.summary("earlier", "a", "b")])
    assert conv[0]["role"] == "user"
    assert "earlier" in conv[0]["content"]


def test_assistant_tool_calls_serialized_as_json_string():
    stream = [
        messages.assistant("calling"),
        messages.tool_call("read", "c1", {"path": "a.txt"}),
    ]
    conv = to_openai(stream)
    entry = conv[0]
    assert entry["role"] == "assistant"
    assert entry["content"] == "calling"
    call = entry["tool_calls"][0]
    assert call["id"] == "c1"
    assert call["type"] == "function"
    assert call["function"]["name"] == "read"
    assert json.loads(call["function"]["arguments"]) == {"path": "a.txt"}


def test_tool_result_becomes_tool_role():
    conv = to_openai([messages.tool_result("read", "c1", "file body")])
    assert conv == [{"role": "tool", "tool_call_id": "c1", "content": "file body"}]


def test_assistant_only_tool_calls_has_null_content():
    stream = [
        messages.assistant(""),
        messages.tool_call("bash", "c1", {"command": "ls"}),
    ]
    conv = to_openai(stream)
    assert conv[0]["content"] is None
    assert conv[0]["tool_calls"][0]["function"]["name"] == "bash"


def test_empty_assistant_without_tools_gets_empty_string():
    conv = to_openai([messages.assistant("")])
    assert conv[0]["content"] == ""
