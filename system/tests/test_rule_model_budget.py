"""Local CodeQL work must not exhaust a rule's model recovery budget."""

import pytest

from app.adapters.ai.policy import CallBudget, policy_snapshot
from app.domain.audit import AuditError


def test_rule_budget_excludes_codeql_but_bounds_model_calls(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("app.adapters.ai.policy.monotonic", lambda: clock[0])
    policy = {**policy_snapshot("rule"), "max_seconds": 30, "timeout": 20}
    records = [{"input_tokens": 10, "output_tokens": 10, "seconds": 5}]
    budget = CallBudget(policy, records)
    clock[0] = 600  # A real compilation and positive/negative fixture run.
    assert budget.reserve(100, 100) == 20
    records[0]["seconds"] = 31
    with pytest.raises(AuditError, match="seconds="):
        budget.reserve(100, 100)


def test_frozen_old_rule_policy_keeps_wall_time_limit(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("app.adapters.ai.policy.monotonic", lambda: clock[0])
    policy = {**policy_snapshot("rule"), "max_seconds": 30}
    policy.pop("seconds_scope")
    budget = CallBudget(policy, [])
    clock[0] = 31
    with pytest.raises(AuditError, match="seconds="):
        budget.reserve(100, 100)
