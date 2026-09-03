from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class ApprovalMode(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass
class ApprovalDecision:
    tool: str
    allowed: bool
    mode: str
    reason: str


class ApprovalPolicy:
    def __init__(self, rules: dict[str, str], default: str = ApprovalMode.ASK):
        self.rules = dict(rules)
        self.default = default

    def mode_for(self, tool: str) -> str:
        return self.rules.get(tool, self.default)

    @classmethod
    def default(cls) -> "ApprovalPolicy":
        return cls(
            {
                "read": ApprovalMode.ALLOW,
                "grep": ApprovalMode.ALLOW,
                "write": ApprovalMode.ASK,
                "bash": ApprovalMode.ASK,
            },
            default=ApprovalMode.ASK,
        )

    @classmethod
    def auto_approve(cls) -> "ApprovalPolicy":
        return cls({}, default=ApprovalMode.ALLOW)


Asker = Callable[[str, dict[str, Any]], bool]


class ApprovalGate:
    def __init__(self, policy: ApprovalPolicy, asker: Asker | None = None):
        self.policy = policy
        self.asker = asker

    def check(self, tool: str, args: dict[str, Any]) -> ApprovalDecision:
        mode = self.policy.mode_for(tool)
        if mode == ApprovalMode.ALLOW:
            return ApprovalDecision(tool, True, mode, "auto-approved by policy")
        if mode == ApprovalMode.DENY:
            return ApprovalDecision(tool, False, mode, "denied by policy")
        if self.asker is None:
            return ApprovalDecision(
                tool, False, mode, "approval required but no approver configured"
            )
        allowed = bool(self.asker(tool, args))
        return ApprovalDecision(
            tool, allowed, mode, "approved by user" if allowed else "rejected by user"
        )


__all__ = [
    "ApprovalMode",
    "ApprovalDecision",
    "ApprovalPolicy",
    "ApprovalGate",
    "Asker",
]
