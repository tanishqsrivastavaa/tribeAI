from tribe.models import ModelResponse, ScriptedModel, ToolCall
from tribe.sessions import messages


def test_replays_steps_in_order():
    model = ScriptedModel([ModelResponse(text="first"), ModelResponse(text="second")])
    assert model.complete("s", [messages.user("a")]).text == "first"
    assert model.complete("s", [messages.user("b")]).text == "second"


def test_records_calls():
    model = ScriptedModel([ModelResponse(text="x")])
    model.complete("sys", [messages.user("hi")], tools=[{"name": "read"}])
    assert model.calls[0]["system"] == "sys"
    assert model.calls[0]["tools"] == [{"name": "read"}]


def test_callable_step_sees_messages():
    def step(msgs):
        return ModelResponse(text=f"saw {len(msgs)} messages")

    model = ScriptedModel([step])
    result = model.complete("s", [messages.user("a"), messages.user("b")])
    assert result.text == "saw 2 messages"


def test_exhausted_steps_return_empty():
    model = ScriptedModel([])
    assert model.complete("s", []).text == ""


def test_tool_call_step():
    model = ScriptedModel(
        [ModelResponse(tool_calls=[ToolCall("c1", "bash", {"command": "ls"})])]
    )
    result = model.complete("s", [])
    assert result.wants_tools
    assert result.tool_calls[0].name == "bash"
