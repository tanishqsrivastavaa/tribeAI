from tribe.sessions import messages
from tribe.sessions.messages import Message, Role, ToolStatus


def test_roundtrip_user_message():
    msg = messages.user("hello")
    restored = Message.from_dict(msg.to_dict())
    assert restored.role is Role.USER
    assert restored.content == "hello"
    assert restored.id == msg.id


def test_to_dict_omits_none_fields():
    data = messages.user("hi").to_dict()
    assert "tool_name" not in data
    assert "result" not in data
    assert data["role"] == "user"


def test_tool_call_roundtrip():
    msg = messages.tool_call("read", "call_1", {"path": "a.txt"})
    restored = Message.from_dict(msg.to_dict())
    assert restored.role is Role.TOOL_CALL
    assert restored.tool_name == "read"
    assert restored.call_id == "call_1"
    assert restored.arguments == {"path": "a.txt"}


def test_tool_result_status_roundtrip():
    msg = messages.tool_result("bash", "call_2", "boom", ToolStatus.ERROR, "exit 1")
    restored = Message.from_dict(msg.to_dict())
    assert restored.status is ToolStatus.ERROR
    assert restored.error == "exit 1"
    assert restored.result == "boom"


def test_summary_carries_range():
    msg = messages.summary("did stuff", "id_a", "id_b")
    restored = Message.from_dict(msg.to_dict())
    assert restored.role is Role.SUMMARY
    assert restored.summary_start == "id_a"
    assert restored.summary_end == "id_b"


def test_ids_are_unique():
    assert messages.user("a").id != messages.user("b").id
