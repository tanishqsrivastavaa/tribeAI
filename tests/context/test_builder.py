from tribe.context.builder import ContextBuilder
from tribe.sessions import messages
from tribe.sessions.messages import Role


def test_effective_history_without_summary_drops_system():
    stream = [messages.system("sys"), messages.user("hi"), messages.assistant("yo")]
    history = ContextBuilder().effective_history(stream)
    assert [m.role for m in history] == [Role.USER, Role.ASSISTANT]


def test_effective_history_replaces_covered_prefix_with_summary():
    stream = [messages.user(f"m{i}") for i in range(6)]
    end_id = stream[3].id
    summary = messages.summary("compacted", stream[0].id, end_id)
    stream_with_summary = stream + [summary]  # summary appended last

    history = ContextBuilder().effective_history(stream_with_summary)
    assert history[0].role == Role.SUMMARY
    assert [m.content for m in history[1:]] == ["m4", "m5"]


def test_effective_history_uses_latest_summary():
    stream = [messages.user(f"m{i}") for i in range(6)]
    s1 = messages.summary("first", stream[0].id, stream[1].id)
    s2 = messages.summary("second", stream[0].id, stream[3].id)
    combined = stream + [s1, s2]

    history = ContextBuilder().effective_history(combined)
    assert history[0].content == "second"
    assert [m.content for m in history[1:]] == ["m4", "m5"]


def test_should_compact_false_when_small():
    stream = [messages.user("hi")]
    assert not ContextBuilder(keep_recent=16).should_compact(stream, 1_000_000)


def test_should_compact_true_over_budget():
    stream = [messages.user("x" * 5000) for _ in range(50)]
    builder = ContextBuilder(keep_recent=4, threshold=0.6)
    assert builder.should_compact(stream, 10_000)


def test_should_compact_false_when_within_keep_recent():
    stream = [messages.user("x" * 5000) for _ in range(3)]
    builder = ContextBuilder(keep_recent=16, threshold=0.6)
    assert not builder.should_compact(stream, 10)


def test_build_returns_instructions_and_history():
    builder = ContextBuilder(instructions="be good")
    system, history = builder.build([messages.user("hi")])
    assert system == "be good"
    assert [m.content for m in history] == ["hi"]
