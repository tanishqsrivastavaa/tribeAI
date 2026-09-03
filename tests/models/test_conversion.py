from tribe.models.anthropic_model import to_anthropic
from tribe.sessions import messages
from tribe.sessions.messages import ToolStatus


def test_user_and_assistant_text():
    conv = to_anthropic([messages.user("hi"), messages.assistant("hello")])
    assert conv == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": [{"type": "text", "text": "hello"}]},
    ]


def test_system_messages_are_dropped():
    conv = to_anthropic([messages.system("instructions"), messages.user("hi")])
    assert conv == [{"role": "user", "content": "hi"}]


def test_summary_becomes_user_context():
    conv = to_anthropic([messages.summary("earlier stuff", "a", "b")])
    assert conv[0]["role"] == "user"
    assert "earlier stuff" in conv[0]["content"]


def test_assistant_with_tool_calls_grouped():
    stream = [
        messages.user("read a"),
        messages.assistant("let me read"),
        messages.tool_call("read", "call_1", {"path": "a.txt"}),
        messages.tool_call("read", "call_2", {"path": "b.txt"}),
    ]
    conv = to_anthropic(stream)
    assistant = conv[1]
    assert assistant["role"] == "assistant"
    assert assistant["content"][0] == {"type": "text", "text": "let me read"}
    tool_uses = [b for b in assistant["content"] if b["type"] == "tool_use"]
    assert [b["id"] for b in tool_uses] == ["call_1", "call_2"]
    assert tool_uses[0]["input"] == {"path": "a.txt"}


def test_tool_results_grouped_into_one_user_turn():
    stream = [
        messages.tool_result("read", "call_1", "content-a"),
        messages.tool_result("read", "call_2", "boom", ToolStatus.ERROR, "err"),
    ]
    conv = to_anthropic(stream)
    assert len(conv) == 1
    results = conv[0]["content"]
    assert conv[0]["role"] == "user"
    assert results[0] == {
        "type": "tool_result",
        "tool_use_id": "call_1",
        "content": "content-a",
        "is_error": False,
    }
    assert results[1]["is_error"] is True


def test_assistant_with_only_tool_calls_has_no_empty_text():
    stream = [
        messages.assistant(""),
        messages.tool_call("bash", "c1", {"command": "ls"}),
    ]
    conv = to_anthropic(stream)
    assert conv[0]["content"] == [
        {"type": "tool_use", "id": "c1", "name": "bash", "input": {"command": "ls"}}
    ]


def test_full_roundtrip_shape():
    stream = [
        messages.user("do it"),
        messages.assistant("ok"),
        messages.tool_call("bash", "c1", {"command": "ls"}),
        messages.tool_result("bash", "c1", "files"),
        messages.assistant("done"),
    ]
    conv = to_anthropic(stream)
    assert [c["role"] for c in conv] == ["user", "assistant", "user", "assistant"]
