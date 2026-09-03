from tribe.models import ModelResponse, ScriptedModel, ToolCall
from tribe.observability import Observer


class RecordingObserver(Observer):
    def __init__(self):
        self.events = []

    def run_start(self, session_id, user_input):
        self.events.append(("run_start", user_input))

    def model_response(self, response):
        self.events.append(("model_response", response.stop_reason))

    def tool_start(self, name, args):
        self.events.append(("tool_start", name))

    def tool_end(self, name, result, duration):
        self.events.append(("tool_end", name, result.is_error))

    def run_end(self, result):
        self.events.append(("run_end", result.status))


def test_observer_receives_lifecycle_events(make_loop):
    (make_loop.workspace.root / "a.txt").write_text("hi")
    model = ScriptedModel(
        [
            ModelResponse(tool_calls=[ToolCall("c1", "read", {"path": "a.txt"})], stop_reason="tool_use"),
            ModelResponse(text="ok"),
        ]
    )
    observer = RecordingObserver()
    loop = make_loop(model, observer=observer)
    sid = loop.store.create()

    loop.run(sid, "go")

    names = [e[0] for e in observer.events]
    assert names[0] == "run_start"
    assert "tool_start" in names
    assert "tool_end" in names
    assert observer.events[-1] == ("run_end", "completed")
