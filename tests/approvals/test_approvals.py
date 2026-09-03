from tribe.approvals import ApprovalGate, ApprovalMode, ApprovalPolicy


def test_default_policy_modes():
    policy = ApprovalPolicy.default()
    assert policy.mode_for("read") == ApprovalMode.ALLOW
    assert policy.mode_for("grep") == ApprovalMode.ALLOW
    assert policy.mode_for("write") == ApprovalMode.ASK
    assert policy.mode_for("bash") == ApprovalMode.ASK


def test_unknown_tool_defaults_to_ask():
    assert ApprovalPolicy.default().mode_for("mystery") == ApprovalMode.ASK


def test_allow_is_auto_approved():
    gate = ApprovalGate(ApprovalPolicy.default())
    decision = gate.check("read", {"path": "a"})
    assert decision.allowed
    assert decision.mode == ApprovalMode.ALLOW


def test_ask_without_approver_is_denied():
    gate = ApprovalGate(ApprovalPolicy.default())
    decision = gate.check("bash", {"command": "ls"})
    assert not decision.allowed
    assert "no approver" in decision.reason


def test_ask_invokes_approver():
    calls = []

    def asker(tool, args):
        calls.append((tool, args))
        return True

    gate = ApprovalGate(ApprovalPolicy.default(), asker=asker)
    decision = gate.check("write", {"path": "f"})
    assert decision.allowed
    assert calls == [("write", {"path": "f"})]


def test_ask_rejected_by_user():
    gate = ApprovalGate(ApprovalPolicy.default(), asker=lambda t, a: False)
    decision = gate.check("bash", {"command": "rm -rf /"})
    assert not decision.allowed
    assert decision.reason == "rejected by user"


def test_auto_approve_policy():
    gate = ApprovalGate(ApprovalPolicy.auto_approve())
    assert gate.check("bash", {"command": "ls"}).allowed


def test_deny_policy_blocks():
    gate = ApprovalGate(ApprovalPolicy({"bash": ApprovalMode.DENY}))
    decision = gate.check("bash", {"command": "ls"})
    assert not decision.allowed
    assert decision.mode == ApprovalMode.DENY
