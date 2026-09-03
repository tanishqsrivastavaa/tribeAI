import pytest

from tribe.agent import AgentLoop
from tribe.approvals import ApprovalGate, ApprovalPolicy
from tribe.sessions import SessionStore
from tribe.workspace import Workspace


@pytest.fixture
def make_loop(tmp_path):
    ws_dir = tmp_path / "ws"
    ws_dir.mkdir()
    store = SessionStore(tmp_path / "sessions")

    def factory(model, gate=None, limits=None, builder=None, observer=None):
        return AgentLoop(
            model=model,
            workspace=Workspace(ws_dir),
            store=store,
            gate=gate or ApprovalGate(ApprovalPolicy.auto_approve()),
            limits=limits,
            builder=builder,
            observer=observer,
        )

    factory.store = store
    factory.workspace = Workspace(ws_dir)
    return factory
