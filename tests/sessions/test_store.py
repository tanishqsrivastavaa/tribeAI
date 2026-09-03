import pytest

from tribe.sessions import messages
from tribe.sessions.store import SessionStore


def test_create_and_load_empty(tmp_path):
    store = SessionStore(tmp_path)
    sid = store.create()
    assert store.exists(sid)
    assert store.load(sid) == []


def test_append_and_reload_preserves_order(tmp_path):
    store = SessionStore(tmp_path)
    sid = store.create()
    store.append(sid, messages.user("first"))
    store.append(sid, messages.assistant("second"))

    loaded = store.load(sid)
    assert [m.content for m in loaded] == ["first", "second"]


def test_load_survives_new_store_instance(tmp_path):
    store = SessionStore(tmp_path)
    sid = store.create()
    store.append(sid, messages.user("persisted"))

    reopened = SessionStore(tmp_path)
    assert [m.content for m in reopened.load(sid)] == ["persisted"]


def test_append_to_unknown_session_raises(tmp_path):
    store = SessionStore(tmp_path)
    with pytest.raises(FileNotFoundError):
        store.append("nope", messages.user("x"))


def test_create_duplicate_raises(tmp_path):
    store = SessionStore(tmp_path)
    sid = store.create("fixed")
    with pytest.raises(FileExistsError):
        store.create(sid)


def test_list_sessions(tmp_path):
    store = SessionStore(tmp_path)
    store.create("a")
    store.create("b")
    assert store.list_sessions() == ["a", "b"]


def test_tool_result_persists_structured_fields(tmp_path):
    store = SessionStore(tmp_path)
    sid = store.create()
    store.append(
        sid,
        messages.tool_result("bash", "c1", "out", messages.ToolStatus.ERROR, "err"),
    )
    loaded = store.load(sid)[0]
    assert loaded.status is messages.ToolStatus.ERROR
    assert loaded.error == "err"
