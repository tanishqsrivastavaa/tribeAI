from tribe.context.builder import ContextBuilder
from tribe.context.compaction import compact, render_transcript
from tribe.models import ModelResponse, ScriptedModel
from tribe.sessions import messages
from tribe.sessions.messages import Role, ToolStatus


def test_render_transcript_covers_roles():
    stream = [
        messages.user("goal"),
        messages.assistant("thinking"),
        messages.tool_call("bash", "c1", {"command": "ls"}),
        messages.tool_result("bash", "c1", "out", ToolStatus.ERROR, "err"),
    ]
    text = render_transcript(stream)
    assert "User: goal" in text
    assert "Assistant: thinking" in text
    assert "Tool call bash" in text
    assert "Tool result [error]" in text


def test_compact_none_when_short():
    model = ScriptedModel([ModelResponse(text="summary")])
    assert compact(model, [messages.user("hi")], keep_recent=16) is None


def test_compact_produces_summary_with_range():
    stream = [messages.user(f"m{i}") for i in range(10)]
    model = ScriptedModel([ModelResponse(text="dense summary")])
    summary = compact(model, stream, keep_recent=3)
    assert summary.role == Role.SUMMARY
    assert summary.content == "dense summary"
    assert summary.summary_start == stream[0].id
    assert summary.summary_end == stream[6].id  # last of the older span


def test_compaction_cycle_shrinks_effective_history():
    stream = [messages.user(f"m{i}") for i in range(10)]
    model = ScriptedModel([ModelResponse(text="SUMMARY OF m0..m6")])
    builder = ContextBuilder(keep_recent=3)

    summary = compact(model, builder.effective_history(stream), keep_recent=3)
    stream.append(summary)  # append-only, as the store would

    history = builder.effective_history(stream)
    assert history[0].content == "SUMMARY OF m0..m6"
    assert [m.content for m in history[1:]] == ["m7", "m8", "m9"]


def test_summarizer_receives_older_span_only():
    stream = [messages.user(f"m{i}") for i in range(6)]
    model = ScriptedModel([ModelResponse(text="s")])
    compact(model, stream, keep_recent=2)
    sent = model.calls[0]["messages"][0].content
    assert "m0" in sent and "m3" in sent
    assert "m4" not in sent and "m5" not in sent
