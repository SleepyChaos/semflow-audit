"""Source identity, independent verdict failures and bounded recovery regression tests."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.adapters.operation_evidence import locate_quote
from app.contracts.discovery_semantics import PremiseCheck, ScoutResponseV6
from app.contracts.review import PrimaryLocation
from app.domain.audit import AuditError
from app.services.discovery_context import validate_premises
from app.services.scout_inspection import validate_checks

from tests.test_dual_discovery import run_scout
from tests.test_unified_review import ReviewModel, run_review


class SemanticModel(ReviewModel):
    def generate(self, purpose, payload, schema):
        self.usage["calls"] += 1
        self.seen.append(payload)
        code = [m for m in payload["evidence"] if m["kind"] == "code"]
        ids = [m["id"] for m in code]
        quote = "value = eval(input())"
        return schema.model_validate(
            {
                "action": "final",
                "candidate_assessments": [
                    {
                        "candidate_id": t["candidate_id"],
                        "assessment": "supported",
                        "weakness": "CWE-94",
                        "reason": "Actual input reaches the bound eval operation.",
                        "checked_premises": [
                            "Actual source operation and input were checked."
                        ],
                        "evidence_ids": ids,
                        "security_property": t["security_property"],
                        "premises": [
                            {
                                "premise": role,
                                "status": "established",
                                "reason": "Actual supplied code establishes this local premise.",
                                "evidence_ids": ids,
                                "quote": quote,
                            }
                            for role in (
                                "operation",
                                "input_or_policy",
                                "unsafe_protection",
                            )
                        ],
                    }
                    for t in payload["targets"]
                ],
            }
        )


def test_invalid_candidate_is_isolated_and_only_it_is_recovered(pipeline_context):
    run_scout(pipeline_context)

    class InvalidOnce(SemanticModel):
        def generate(self, purpose, payload, schema):
            result = super().generate(purpose, payload, schema)
            if len(payload["targets"]) > 1:
                result.candidate_assessments[-1].evidence_ids = [uuid4()]
            return result

    provider = InvalidOnce()
    provider.policy = {"max_calls": 3}
    service = run_review(pipeline_context, provider, version="8", discover=False)
    result = service.repository.get(service.stage_id).result
    assert (
        len(result["recommendations"]) == 2 and not result["unreviewed_candidate_ids"]
    ), result["batches"]
    assert len(result["batches"][0]["rejected_assessments"]) == 1
    assert (
        len(provider.seen[0]["targets"]) == 2 and len(provider.seen[1]["targets"]) == 1
    )
    assert len(result["recovery_attempted_ids"]) == 1
    from app.workflows.review import build_review_graph

    build_review_graph(service).invoke({"stage_id": service.stage_id})
    assert provider.usage["calls"] == 2


def test_recovery_cannot_expand_call_cap(pipeline_context):
    class Omitted(SemanticModel):
        def generate(self, purpose, payload, schema):
            self.usage["calls"] += 1
            return schema.model_validate({"action": "final"})

    provider = Omitted()
    provider.policy = {"max_calls": 1}
    service = run_review(pipeline_context, provider, version="8", discover=False)
    result = service.repository.get(service.stage_id).result
    assert provider.usage["calls"] == 1 and result["unreviewed_candidate_ids"]
    assert not result.get("recovery_attempted_ids")


def test_optional_invalid_finding_preserves_valid_verdict(pipeline_context):
    class InvalidExtra(SemanticModel):
        def generate(self, purpose, payload, schema):
            result = super().generate(purpose, payload, schema)
            data = result.model_dump(mode="json")
            data["new_findings"] = [
                {
                    "title": "Unprovided optional finding",
                    "description": "Source has not been supplied for this hypothesis.",
                    "weakness": "CWE-20",
                    "related_target": payload["targets"][0]["candidate_id"],
                    "primary_location": {"file": "app.py", "line": 1},
                    "evidence_ids": [str(uuid4())],
                }
            ]
            return schema.model_validate(data)

    service = run_review(pipeline_context, InvalidExtra(), version="8", discover=False)
    result = service.repository.get(service.stage_id).result
    assert len(result["recommendations"]) == 1, result["batches"]
    assert result["batches"][0]["rejected_new_findings"]


def test_exact_quote_corrects_line_and_ambiguous_quote_stays_unknown():
    row = SimpleNamespace(
        primary_location=PrimaryLocation(file="app.py", line=2),
        operation_quote="value = rp(input())",
        evidence_ids=["source"],
    )
    context = {
        "snapshot": "s",
        "evidence": [
            {
                "id": "source",
                "kind": "code",
                "reference": {"file": "app.py", "start_line": 1},
                "content": "def handle():\n    data = input()\n    value = rp(input())",
            }
        ],
    }
    assert locate_quote(row, context, "python")["line"] == 3
    context["evidence"][0]["content"] += "\nvalue = rp(input())"
    row.primary_location.line = 1
    with pytest.raises(AuditError, match="多处"):
        locate_quote(row, context, "python")


def test_semantic_task_cannot_claim_inspection_from_readme():
    context = {
        "language": "python",
        "inspection_tasks": [{"id": "authorization"}],
        "evidence": [
            {"id": str(uuid4()), "kind": "code", "reference": {"file": "README.md"}}
        ],
    }
    response = ScoutResponseV6.model_validate(
        {
            "action": "final",
            "task_checks": [
                {
                    "task_id": "authorization",
                    "status": "investigated",
                    "reason": "The README describes application authorization.",
                    "evidence_ids": [context["evidence"][0]["id"]],
                }
            ],
        }
    )
    with pytest.raises(AuditError, match="源码"):
        validate_checks(response, context, semantic=True)


def test_local_missing_protection_or_property_swap_cannot_support():
    source_id = uuid4()
    rows = [
        {
            "id": str(source_id),
            "kind": "code",
            "reference": {"file": "app.py"},
            "content": "login_required(handler)",
        }
    ]
    target = {
        "security_property": "authorization",
        "required_premises": ["operation", "input_or_policy", "unsafe_protection"],
    }
    assessment = SimpleNamespace(
        security_property="authorization",
        assessment="supported",
        premises=[
            PremiseCheck(
                premise=role,
                status="established",
                reason="Source shows a login check but no role verification.",
                evidence_ids=[source_id],
                quote="login_required(handler)",
            )
            for role in target["required_premises"]
        ],
    )
    context = {
        "language": "python",
        "local_control_context": {"missing_modules": [{"file": "guards.py"}]},
    }
    with pytest.raises(AuditError, match="本地源码"):
        validate_premises(assessment, target, context, lambda ids: rows)
    assessment.security_property = "authentication"
    with pytest.raises(AuditError, match="属性不一致"):
        validate_premises(assessment, target, context, lambda ids: rows)


def test_route_parsers_enumerate_sensitive_endpoints_without_inventing_guards():
    from app.adapters.route_inventory import javascript_routes, python_routes

    py = "@app.route('/a', methods=['POST'])\ndef a():\n    return compute()\n@app.route('/b')\n@guard\ndef b():\n    return 'ok'\n"
    rows = python_routes(py)
    assert [(r["endpoint"], r["methods"]) for r in rows] == [
        ("/a", ["POST"]),
        ("/b", ["GET"]),
    ]
    js = "router.get('/logout', function(req,res){req.logout()});\nrouter.post('/login', guard, login);"
    rows = javascript_routes(js)
    assert [(r["endpoint"], r["methods"]) for r in rows] == [
        ("/logout", ["GET"]),
        ("/login", ["POST"]),
    ]
    assert not javascript_routes("const x = fake.get('settings')")


def test_bundled_authentication_cannot_complete_two_route_checks():
    from app.contracts.discovery_semantics import ScoutResponseV6
    from app.services.route_obligations import validate_routes

    eid = str(uuid4())
    routes = [
        {
            "route_id": "a",
            "endpoint": "/a",
            "file": "app.py",
            "start_line": 1,
            "end_line": 3,
        },
        {
            "route_id": "b",
            "endpoint": "/b",
            "file": "app.py",
            "start_line": 4,
            "end_line": 6,
        },
    ]
    context = {
        "route_inventory": {"routes": routes},
        "evidence": [
            {
                "id": eid,
                "kind": "code",
                "reference": {"file": "app.py", "start_line": 1, "end_line": 6},
            }
        ],
    }
    response = ScoutResponseV6.model_validate(
        {
            "action": "final",
            "task_checks": [
                {
                    "task_id": "authentication",
                    "status": "unknown",
                    "reason": "Other properties are not resolved yet.",
                }
            ],
            "route_checks": [
                {
                    "route_id": r["route_id"],
                    "authentication": "missing_authentication",
                    "reason": "This sensitive route has no local authentication check.",
                    "evidence_ids": [eid],
                }
                for r in routes
            ],
            "findings": [
                {
                    "title": "Both routes lack authentication",
                    "weakness": "CWE-306",
                    "security_property": "authentication",
                    "endpoint": "/a",
                    "primary_location": {"file": "app.py", "line": 1},
                    "security_condition": "Sensitive operations require authenticated access.",
                    "observation": "Both endpoints appear to lack local authentication guards.",
                    "operation_quote": "@app.route('/a')",
                    "evidence_ids": [eid],
                }
            ],
        }
    )
    with pytest.raises(AuditError, match="独立候选"):
        validate_routes(response, context)


def test_target_citations_are_refreshed_after_page_replacement():
    from app.services.discovery_context import refresh_citation_contract

    ctx = {
        "targets": [
            {
                "candidate_id": "t",
                "location": {"file": "app.py", "line": 7},
                "evidence_ids": ["old"],
            }
        ],
        "evidence": [
            {
                "id": "new",
                "kind": "code",
                "reference": {"file": "app.py", "start_line": 1, "end_line": 10},
            }
        ],
        "citation_contract": {"target_source_ids": {"t": ["old"]}},
    }
    result = refresh_citation_contract(ctx)
    assert result["targets"][0]["evidence_ids"] == ["new"]
    assert result["citation_contract"]["target_source_ids"] == {"t": ["new"]}


def test_structured_premise_citations_are_retained_without_weakening_grounding():
    from app.contracts.discovery_semantics import SemanticAssessment
    from app.services.read_tools import grounded
    from app.services.review_verdict_gate import validate_assessment

    first, last = uuid4(), uuid4()
    rows = [
        {
            "id": str(first),
            "kind": "code",
            "reference": {"file": "app.py", "start_line": 1, "end_line": 1},
            "content": "import flask",
        },
        {
            "id": str(last),
            "kind": "code",
            "reference": {"file": "app.py", "start_line": 208, "end_line": 208},
            "content": "app.debug = True",
        },
    ]
    candidate_id = uuid4()
    target = {
        "security_property": "secrets_config",
        "required_premises": ["operation", "input_or_policy", "unsafe_protection"],
        "location": {"file": "app.py", "line": 208},
    }
    assessment = SemanticAssessment(
        candidate_id=candidate_id,
        weakness="CWE-489",
        assessment="supported",
        reason="The actual source explicitly enables the debug configuration.",
        checked_premises=["Configuration source checked."],
        evidence_ids=[first],
        security_property="secrets_config",
        premises=[
            {
                "premise": role,
                "status": "established",
                "reason": "This actual configuration establishes the vulnerability condition.",
                "evidence_ids": [last],
                "quote": "app.debug = True",
            }
            for role in target["required_premises"]
        ],
    )

    def evidence(ids, location=None):
        assert set(map(str, ids)) <= {r["id"] for r in rows}
        selected = [r for r in rows if r["id"] in set(map(str, ids))]
        if location and not grounded(selected, location):
            raise AuditError("No target source")
        return selected

    service = SimpleNamespace(stage=SimpleNamespace(prompt_version="8"))
    validate_assessment(
        service,
        assessment,
        {"language": "python", "evidence": rows},
        {str(candidate_id): target},
        evidence,
    )
    assert set(assessment.evidence_ids) == {first, last}
    assessment.premises[0].evidence_ids = [uuid4()]
    with pytest.raises(AssertionError):
        validate_assessment(
            service,
            assessment,
            {"language": "python", "evidence": rows},
            {str(candidate_id): target},
            evidence,
        )


def test_bad_task_receipt_preserves_independent_logging_finding():
    from app.contracts.discovery_semantics import SemanticTaskCheck
    from app.services.route_obligations import reconcile_receipts

    eid = uuid4()
    logging_finding = SimpleNamespace(security_property="security_logging")
    response = SimpleNamespace(
        findings=[logging_finding],
        route_checks=[],
        task_checks=[
            SemanticTaskCheck(
                task_id=prop,
                status="investigated",
                conclusion="suspicious",
                reason="The inspected source indicates a suspicious condition.",
                evidence_ids=[eid],
            )
            for prop in ("authorization", "security_logging")
        ],
    )
    context = {
        "language": "javascript",
        "route_inventory": {"routes": []},
        "inspection_tasks": [{"id": p} for p in ("authorization", "security_logging")],
        "evidence": [
            {"id": str(eid), "kind": "code", "reference": {"file": "passport.js"}}
        ],
    }
    rejected = reconcile_receipts(response, context)
    assert response.findings == [logging_finding]
    assert response.task_checks[0].status == "unknown"
    assert response.task_checks[0].conclusion == "unknown"
    assert response.task_checks[1].status == "investigated"
    assert rejected[0]["id"] == "authorization"


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "def handle():\n    print('event')\n    print('event')\n"}],
    indirect=True,
)
@pytest.mark.parametrize(
    "cap, expected_calls, expected_findings", [(1, 1, 1), (2, 2, 2), (3, 1, 1)]
)
def test_scout_localization_retry_is_bounded_and_preserves_valid_candidates(
    pipeline_context, cap, expected_calls, expected_findings, monkeypatch
):
    from tests.test_dual_discovery import HypothesisModel

    class AmbiguousOnce(HypothesisModel):
        def generate(self, purpose, payload, schema):
            response = super().generate(purpose, payload, schema)
            data = response.model_dump(mode="json")
            proposal = dict(data["findings"][0])
            proposal.update(
                title="Security event recording hypothesis",
                weakness="CWE-778",
                security_property="security_logging",
                operation_quote="print('event')",
                primary_location={
                    "file": "app.py",
                    "line": 2 if self.usage["calls"] == 2 else 1,
                },
            )
            data["findings"].append(proposal)
            return schema.model_validate(data)

    if cap == 3:
        monkeypatch.setattr(
            "app.services.scout_localization.localization_feedback",
            lambda *_: {"repairs": "x" * 30000},
        )
    model = AmbiguousOnce()
    model.policy = {"max_calls": cap}
    service = run_scout(
        pipeline_context,
        model,
        version="6",
        max_units=1,
        steps_per_unit=3,
        max_context_chars=20000,
    )
    result = service.repository.get(service.stage_id).result
    assert model.usage["calls"] == expected_calls
    assert len(result["units"][0]["hypotheses"]) == expected_findings
    if cap == 2:
        feedback = model.seen[1]["server_feedback"]["repairs"][0]
        assert [r["line"] for r in feedback["actual_occurrences"]] == [2, 3]
        assert feedback["reason"].startswith("操作引用在多处")
