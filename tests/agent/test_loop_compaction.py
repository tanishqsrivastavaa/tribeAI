from tribe.agent import RunStatus
from tribe.context import ContextBuilder
from tribe.context.compaction import SUMMARY_SYSTEM
from tribe.models import ModelResponse, ScriptedModel
from tribe.sessions import messages
from tribe.sessions.messages import Role


def test_compaction_runs_during_loop(make_loop):
    model = ScriptedModel(
        [ModelResponse(text="COMPACT SUMMARY"), ModelResponse(text="done")],
        context_limit=50,
    )
    builder = ContextBuilder(keep_recent=3, threshold=0.6)
    loop = make_loop(model, builder=builder)
    sid = loop.store.create()

    for i in range(8):
        loop.store.append(sid, messages.user(f"old message number {i} " * 5))

    result = loop.run(sid, "continue")
    assert result.status == RunStatus.COMPLETED
    assert result.final_text == "done"

    summaries = [m for m in loop.store.load(sid) if m.role == Role.SUMMARY]
    assert len(summaries) == 1
    assert summaries[0].content == "COMPACT SUMMARY"

    # the first model call was the compaction summarization
    assert model.calls[0]["system"] == SUMMARY_SYSTEM
