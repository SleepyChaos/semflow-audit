"""Regression coverage for read pagination, binding traps and bounded scheduling."""

import pytest
from app.adapters.python_bindings import binding_clues
from app.services.review_pool import batches

from tests.test_unified_review import ReviewModel, run_review


def test_python_alias_is_not_invented_and_parameter_scope_is_retained():
    missing = "from os import popen\ndef lookup(value):\n    return rp(value)\n"
    assert binding_clues(missing, 3)["direct_calls"] == [
        {"name": "rp", "binding": "no_static_binding"}
    ]
    actual = missing.replace("import popen", "import popen as rp")
    assert binding_clues(actual, 3)["direct_calls"][0]["binding"] == "declared_in_scope"
    parameter = "def wrapper(rp):\n    return rp('x')\n"
    assert (
        binding_clues(parameter, 2)["direct_calls"][0]["binding"] == "declared_in_scope"
    )
    dynamic = "from external import *\nrp('x')\n"
    assert (
        binding_clues(dynamic, 2)["direct_calls"][0]["binding"]
        == "unknown_dynamic_scope"
    )


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "value = eval(input())\n" + "# retained source\n" * 240}],
    indirect=True,
)
def test_large_read_returns_real_pages_without_failing_batch(pipeline_context):
    class Paged(ReviewModel):
        def generate(self, purpose, payload, schema):
            if not payload.get("latest_tool_observation"):
                return schema.model_validate(
                    {
                        "action": "tool",
                        "tool": {
                            "name": "read_source",
                            "arguments": {
                                "file": "app.py",
                                "start_line": 1,
                                "end_line": 241,
                            },
                        },
                    }
                )
            page = payload["latest_tool_observation"].get("pagination", {})
            if page.get("next_start_line"):
                assert page["returned"]["end_line"] == 151
                return schema.model_validate(
                    {
                        "action": "tool",
                        "tool": {
                            "name": "read_source",
                            "arguments": {
                                "file": "app.py",
                                "start_line": 152,
                                "end_line": 241,
                            },
                        },
                    }
                )
            assert any(
                r["reference"].get("start_line") == 152 for r in payload["evidence"]
            )
            return super().generate(purpose, payload, schema)

    service = run_review(pipeline_context, Paged(), version="5")
    result = service.repository.get(service.stage_id).result
    assert (
        result["coverage_status"] == "completed" and len(result["recommendations"]) == 1
    )


def test_invalid_coordinate_is_observation_and_scope_escape_still_rejected(
    pipeline_context,
):
    class Invalid(ReviewModel):
        def generate(self, purpose, payload, schema):
            if not payload.get("latest_tool_observation"):
                return schema.model_validate(
                    {
                        "action": "tool",
                        "tool": {
                            "name": "read_source",
                            "arguments": {
                                "file": "app.py",
                                "start_line": 0,
                                "end_line": 60,
                            },
                        },
                    }
                )
            assert payload["latest_tool_observation"]["status"] == "invalid_arguments"
            return super().generate(purpose, payload, schema)

    service = run_review(pipeline_context, Invalid(), version="5")
    assert (
        service.repository.get(service.stage_id).result["coverage_status"]
        == "completed"
    )

    class Escape(ReviewModel):
        def generate(self, _purpose, _payload, schema):
            return schema.model_validate(
                {
                    "action": "tool",
                    "tool": {
                        "name": "read_source",
                        "arguments": {
                            "file": "../outside.py",
                            "start_line": 1,
                            "end_line": 999,
                        },
                    },
                }
            )

    service = run_review(pipeline_context, Escape(), version="5")
    assert (
        service.repository.get(service.stage_id).result["coverage_status"] == "partial"
    )


def test_scout_priority_preserves_every_candidate_and_explicit_limits():
    pool = {
        "entries": [
            {
                "candidate_id": str(i),
                "origin": "scout" if i == 42 else "static",
                "location": {"file": "app.py", "line": i + 1},
            }
            for i in range(43)
        ]
    }
    schedule = batches(pool, 4, prioritize_scout=True)
    assert schedule[0][0]["candidate_id"] == "42"
    assert len(schedule) == 11 and sum(map(len, schedule)) == 43
    assert sum(map(len, schedule[:4])) == 16


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "from os import popen\ndef lookup(value):\n    return rp(value)\n"}],
    indirect=True,
)
def test_unbound_dangerous_call_cannot_be_supported(pipeline_context):
    from copy import deepcopy

    from app.core.db import engine
    from app.persistence.audit_models import AuditRun
    from sqlmodel import Session

    with Session(engine) as db:
        run = db.get(AuditRun, pipeline_context["run_id"])
        findings = deepcopy(run.findings)
        findings[0]["locations"][0]["line"] = 3
        run.findings = findings
        db.add(run)
        db.commit()

    class Trap(ReviewModel):
        def generate(self, purpose, payload, schema):
            response = super().generate(purpose, payload, schema)
            if payload.get("server_feedback"):
                assert "符号绑定" in payload["server_feedback"]["validation_error"]
                response.candidate_assessments[0].assessment = "insufficient"
                response.candidate_assessments[0].missing_premises = [
                    "rp has no actual binding"
                ]
            return response

    service = run_review(pipeline_context, Trap(), version="5")
    result = service.repository.get(service.stage_id).result
    assert [r["recommendation"] for r in result["recommendations"]] == ["insufficient"]


def test_shadowed_builtin_is_not_reported_as_builtin_dispatch():
    source = "def eval(value):\n    return value\neval('x')\n"
    assert binding_clues(source, 3)["direct_calls"][0]["binding"] == "declared_in_scope"


def test_review_distributes_calls_across_full_pool(pipeline_context):
    from copy import deepcopy

    from app.core.db import engine
    from app.persistence.audit_models import AuditRun
    from sqlmodel import Session

    with Session(engine) as db:
        audit = db.get(AuditRun, pipeline_context["run_id"])
        baseline = deepcopy(audit.findings[0])
        audit.findings = [
            {**deepcopy(baseline), "id": f"static-{i}"} for i in range(43)
        ]
        db.add(audit)
        db.commit()
    provider = ReviewModel()
    provider.policy = {"max_calls": 12}
    service = run_review(pipeline_context, provider, version="6", max_batches=24)
    result = service.repository.get(service.stage_id).result
    assert result["coverage_status"] == "completed"
    assert len(result["recommendations"]) == 43
    assert provider.usage["calls"] == 11
    assert provider.seen[0]["finalize_required"]


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "from os import popen\ndef lookup(value):\n    return rp(value)\n"}],
    indirect=True,
)
def test_unbound_scout_operation_is_retained_outside_active_candidate_pool(
    pipeline_context,
):
    from tests.test_dual_discovery import HypothesisModel, run_scout

    class Unbound(HypothesisModel):
        def generate(self, purpose, payload, schema):
            response = super().generate(purpose, payload, schema)
            response.findings[0].weakness = "CWE-78"
            response.findings[0].primary_location.line = 3
            return response

    service = run_scout(pipeline_context, Unbound(), version="3")
    result = service.repository.get(service.stage_id).result
    assert result["units"][0]["hypotheses"] == []
    assert len(result["units"][0]["binding_unresolved_observations"]) == 1
    assert result["coverage"]["status"] == "completed"
