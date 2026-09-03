from tribe.agent import Cancellation, RunLimits, RunStatus
from tribe.approvals import ApprovalGate, ApprovalPolicy
from tribe.models import ModelResponse, ScriptedModel, ToolCall
from tribe.sessions.messages import Role


def _tool_response(name, args, call_id="c1"):
    return ModelResponse(
        tool_calls=[ToolCall(call_id, name, args)], stop_reason="tool_use"
    )


def test_simple_completion(make_loop):
    model = ScriptedModel([ModelResponse(text="all done")])
    loop = make_loop(model)
    sid = loop.store.create()

    result = loop.run(sid, "hello")
    assert result.status == RunStatus.COMPLETED
    assert result.final_text == "all done"

    roles = [m.role for m in loop.store.load(sid)]
    assert roles == [Role.USER, Role.ASSISTANT]


def test_tool_call_then_completion(make_loop):
    (make_loop.workspace.root / "a.txt").write_text("file body")
    model = ScriptedModel(
        [_tool_response("read", {"path": "a.txt"}), ModelResponse(text="I read it")]
    )
    loop = make_loop(model)
    sid = loop.store.create()

    result = loop.run(sid, "read a.txt")
    assert result.completed
    assert result.final_text == "I read it"

    messages = loop.store.load(sid)
    roles = [m.role for m in messages]
    assert roles == [
        Role.USER,
        Role.ASSISTANT,
        Role.TOOL_CALL,
        Role.TOOL_RESULT,
        Role.ASSISTANT,
    ]
    tool_result = messages[3]
    assert tool_result.result == "file body"
    assert tool_result.status.value == "ok"


def test_denied_approval_blocks_execution(make_loop):
    model = ScriptedModel(
        [
            _tool_response("write", {"path": "x.txt", "content": "data"}),
            ModelResponse(text="blocked"),
        ]
    )
    gate = ApprovalGate(ApprovalPolicy.default())  # no asker -> write denied
    loop = make_loop(model, gate=gate)
    sid = loop.store.create()

    result = loop.run(sid, "write a file")
    assert result.completed
    assert not (make_loop.workspace.root / "x.txt").exists()

    tool_result = [m for m in loop.store.load(sid) if m.role == Role.TOOL_RESULT][0]
    assert tool_result.status.value == "error"
    assert "approval denied" in tool_result.result


def test_max_rounds(make_loop):
    (make_loop.workspace.root / "a.txt").write_text("x")
    steps = [_tool_response("read", {"path": "a.txt"}) for _ in range(10)]
    loop = make_loop(ScriptedModel(steps), limits=RunLimits(max_rounds=3))
    sid = loop.store.create()

    result = loop.run(sid, "loop forever")
    assert result.status == RunStatus.MAX_ROUNDS
    assert result.rounds == 3


def test_max_consecutive_failures(make_loop):
    steps = [_tool_response("bash", {"command": "exit 1"}) for _ in range(5)]
    loop = make_loop(
        ScriptedModel(steps), limits=RunLimits(max_consecutive_failures=2)
    )
    sid = loop.store.create()

    result = loop.run(sid, "run failing commands")
    assert result.status == RunStatus.MAX_CONSECUTIVE_FAILURES


def test_failure_counter_resets_on_success(make_loop):
    (make_loop.workspace.root / "a.txt").write_text("ok")
    steps = [
        _tool_response("bash", {"command": "exit 1"}),
        _tool_response("read", {"path": "a.txt"}),
        _tool_response("bash", {"command": "exit 1"}),
        ModelResponse(text="survived"),
    ]
    loop = make_loop(ScriptedModel(steps), limits=RunLimits(max_consecutive_failures=2))
    sid = loop.store.create()

    result = loop.run(sid, "mixed")
    assert result.completed
    assert result.final_text == "survived"


def test_unknown_tool_is_failure(make_loop):
    steps = [_tool_response("nonexistent", {}), ModelResponse(text="ok")]
    loop = make_loop(ScriptedModel(steps))
    sid = loop.store.create()

    result = loop.run(sid, "call missing tool")
    assert result.completed
    tool_result = [m for m in loop.store.load(sid) if m.role == Role.TOOL_RESULT][0]
    assert "unknown tool" in tool_result.result


def test_cancellation_before_first_round(make_loop):
    loop = make_loop(ScriptedModel([ModelResponse(text="never")]))
    sid = loop.store.create()
    cancel = Cancellation()
    cancel.cancel()

    result = loop.run(sid, "stop", cancellation=cancel)
    assert result.status == RunStatus.CANCELLED
    assert result.rounds == 0


def test_cancellation_during_tool_phase(make_loop):
    cancel = Cancellation()

    def step(_messages):
        cancel.cancel()
        return _tool_response("read", {"path": "a.txt"})

    loop = make_loop(ScriptedModel([step]))
    sid = loop.store.create()

    result = loop.run(sid, "go", cancellation=cancel)
    assert result.status == RunStatus.CANCELLED


def test_parallel_tool_calls_all_executed(make_loop):
    root = make_loop.workspace.root
    model = ScriptedModel(
        [
            ModelResponse(
                tool_calls=[
                    ToolCall("c1", "write", {"path": "one.txt", "content": "1"}),
                    ToolCall("c2", "write", {"path": "two.txt", "content": "2"}),
                ],
                stop_reason="tool_use",
            ),
            ModelResponse(text="wrote both"),
        ]
    )
    loop = make_loop(model)
    sid = loop.store.create()

    result = loop.run(sid, "write two files")
    assert result.completed
    assert (root / "one.txt").read_text() == "1"
    assert (root / "two.txt").read_text() == "2"
