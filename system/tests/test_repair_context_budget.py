"""Source growth may expand context; navigation and old frozen policies may not."""

from app.adapters.repair.context_budget import context_limits


def test_exact_source_can_expand_to_frozen_ceiling():
    policy = {"context_chars": 100, "repair_context_max_chars": 200}
    payload = {
        "evidence": [
            {"kind": "code", "reference": {"file": "a.py"}, "content": "x" * 110}
        ]
    }
    assert (
        context_limits("repair", payload, policy, 180)["status"]
        == "expanded_for_source"
    )
    assert (
        context_limits("repair", payload, policy, 210)["status"] == "rejected_context"
    )
    assert context_limits("rule", payload, policy, 180)["status"] == "rejected_context"


def test_old_policy_or_excess_navigation_cannot_expand():
    payload = {
        "evidence": [
            {"kind": "code", "reference": {"file": "a.py"}, "content": "x" * 50}
        ]
    }
    assert (
        context_limits("repair", payload, {"context_chars": 100}, 140)["status"]
        == "rejected_context"
    )
    assert (
        context_limits(
            "repair",
            payload,
            {"context_chars": 100, "repair_context_max_chars": 200},
            180,
        )["status"]
        == "rejected_context"
    )


def test_progressing_repair_is_not_cut_at_twelve_but_still_has_frozen_limit(tmp_path):
    import json
    from types import SimpleNamespace

    import pytest
    from app.domain.audit import AuditError
    from app.services.context_materials import frozen_call
    from pydantic import BaseModel

    class Output(BaseModel):
        value: str

    calls = []

    def generate(*args):
        calls.append(args)
        return Output(value="actual-result")

    policy = {
        "context_chars": 1000,
        "tool_limit": 8,
        "repair_attempts": 3,
        "repair_call_limit": 14,
    }
    (tmp_path / "semantic-policy.json").write_text(json.dumps(policy))
    provider = SimpleNamespace(generate=generate)
    for i in range(14):
        frozen_call(
            provider,
            "repair",
            {"phase": "propose_patch", "attempt": i},
            Output,
            tmp_path / f"call-{i}",
        )
    assert len(calls) == 14
    # Receipt replay does not count as an additional model request.
    frozen_call(
        provider,
        "repair",
        {"phase": "propose_patch", "attempt": 13},
        Output,
        tmp_path / "call-13",
    )
    assert len(calls) == 14
    with pytest.raises(AuditError, match="调用预算耗尽"):
        frozen_call(
            provider,
            "repair",
            {"phase": "propose_patch", "attempt": 14},
            Output,
            tmp_path / "call-14",
        )
    assert len(calls) == 14


def test_expansion_dispatch_is_measured_and_replay_does_not_rebill(tmp_path):
    import json
    from types import SimpleNamespace

    from app.services.context_materials import frozen_call
    from pydantic import BaseModel

    class Output(BaseModel):
        value: str

    calls = []

    def generate(*args):
        calls.append(args)
        return Output(value="read-result")

    (tmp_path / "semantic-policy.json").write_text(
        json.dumps(
            {
                "context_chars": 200,
                "repair_context_max_chars": 600,
                "tool_limit": 2,
                "repair_attempts": 1,
                "repair_call_limit": 6,
            }
        )
    )
    payload = {
        "phase": "inspect_semantics",
        "evidence": [
            {"kind": "code", "reference": {"file": "a.py"}, "content": "x" * 250}
        ],
    }
    provider = SimpleNamespace(generate=generate)
    assert (
        frozen_call(provider, "repair", payload, Output, tmp_path / "call").value
        == "read-result"
    )
    metrics = json.loads((tmp_path / "call/payload-metrics.json").read_text())
    assert metrics["status"] == "expanded_for_source"
    assert metrics["preferred_limit"] == 200 and metrics["limit"] == 600
    frozen_call(provider, "repair", payload, Output, tmp_path / "call")
    assert len(calls) == 1
