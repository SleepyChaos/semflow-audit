"""Rule preparation boundaries and retry identity; not LLM accuracy evidence."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.domain.audit import AuditError
from app.services.rule_output import assign_namespace
from app.services.rule_preparation_context import preparation_context

from tests.test_rule_synthesis import draft
from tests.test_semantic_development import InspectModel, inspector, make_stage, ready


def test_read_context_reports_actual_eof_and_accepts_separate_api_citation(
    pipeline_context,
):
    api_id = str(uuid4())

    def reply(payload):
        scope = payload["rule_reference_context"]
        assert scope["source_windows"][0]["complete_file"]
        assert scope["source_windows"][0]["total_lines"] == 1
        result = ready(payload)
        result["facts"].append(
            {
                "statement": "Retrieved API declares the source extension point",
                "state": "supported",
                "evidence_ids": [api_id],
                "category": "implementation",
                "critical": False,
            }
        )
        result["unknowns"] = ["Runtime reachability has not been executed"]
        return result

    provider = InspectModel(reply)
    service, source = inspector(pipeline_context, provider)
    context_service = SimpleNamespace(
        inputs=SimpleNamespace(
            source_paths=["app.py"], purpose="vulnerability_detector"
        ),
        audit=service.evidence.audit,
    )
    context = preparation_context(
        context_service,
        {},
        [{"id": api_id, "content": "class Source {}"}],
        service.evidence,
        [source],
    )
    service.reference_context = context
    service.require_grounded_source = True
    result = service.inspect([{"description": "source flow"}], [source])
    assert result["reference_knowledge_ids"] == [api_id]
    assert result["view"]["unknowns"]
    assert service.inspect([{"description": "source flow"}], [source]) == result
    context["knowledge"][0]["content"] = "changed declaration"
    with pytest.raises(AuditError, match="身份变化"):
        service.inspect([{"description": "source flow"}], [source])


def test_knowledge_only_interpretation_cannot_pass_as_project_understanding(
    pipeline_context,
):
    api_id = str(uuid4())

    def reply(payload):
        result = ready(payload)
        result["facts"][0]["evidence_ids"] = [api_id]
        return result

    service, source = inspector(pipeline_context, InspectModel(reply))
    service.reference_context = {
        "knowledge": [{"id": api_id, "content": "class Source {}"}]
    }
    service.require_grounded_source = True
    with pytest.raises(AuditError, match="实际源码引用"):
        service.inspect([{"description": "risk"}], [source])


def test_v8_budget_checks_serialized_model_view_not_pretty_artifact(
    pipeline_context, monkeypatch
):
    from app.services.context_materials import semantic_policy
    from app.services.rule_synthesis import RuleSynthesis
    from app.services.rules import RuleService

    identifier = make_stage(
        pipeline_context,
        "rule",
        "8",
        {
            "requirement": "Inventory eval",
            "purpose": "review_anchor",
            "source_paths": ["app.py"],
        },
    )
    provider = InspectModel(lambda _: draft(str(uuid4())).model_dump(mode="json"))
    service = RuleService(identifier, provider)
    synthesis = RuleSynthesis(service)
    context = {
        "purpose": "review_anchor",
        "strategy": "auto",
        "knowledge": [],
        "padding": [{"a": i, "b": "exact source text"} for i in range(700)],
    }
    limit = semantic_policy(service.directory)["context_chars"]
    assert len(json.dumps(context, ensure_ascii=False, indent=2)) > limit
    assert (
        len(json.dumps({"untrusted_analysis_material": context}, ensure_ascii=False))
        < limit
    )
    monkeypatch.setattr(synthesis, "_context", lambda _: context)
    result = synthesis.propose({})
    assert result["attempt"] == 1
    assert synthesis.propose({}) == result
    assert provider.usage["calls"] == 1
    assert json.loads((service.directory / "draft-0/input.json").read_text()) == context


def test_generated_identity_distinguishes_models_under_same_template_id(tmp_path):
    one = draft(str(uuid4()))
    one.query = (
        "/** @id audit/python-eval-template */\nimport ProjectSource\n" + one.query
    )
    two = one.model_copy(deep=True)
    one.modules = {"ProjectSource.qll": "module source_a {}"}
    two.modules = {"ProjectSource.qll": "module source_b {}"}
    first = assign_namespace(one, tmp_path / "first", unique_logic=True)
    second = assign_namespace(two, tmp_path / "second", unique_logic=True)
    assert (
        first.query.split("@id ")[1].split()[0]
        != second.query.split("@id ")[1].split()[0]
    )
    assert first.query.split("*/", 1)[1] == one.query.split("*/", 1)[1]


def test_cwe943_routes_nosql_without_code_injection_prefix_collision(monkeypatch):
    import app.adapters.retrieval.dual_corpus as dual

    slots = []

    def retrieve(_, owner, language, query, **kwargs):
        slots.append(kwargs)
        return [
            {
                "id": str(uuid4()),
                "document_id": str(uuid4()),
                "version": "current",
                "content": str(kwargs),
                "corpus": kwargs["corpus"],
            }
        ]

    monkeypatch.setattr(dual.KnowledgeRetriever, "retrieve", retrieve)
    monkeypatch.setattr(dual, "complete_document", lambda _, row: row)
    dual.retrieve_both(
        uuid4(),
        "javascript",
        "CWE-943 NoSQL injection query",
        "fixed",
        mode="bm25",
        enhanced=True,
        exact_cwe=True,
    )
    assert any(s.get("example_cwe") == "CWE-943" for s in slots)
    assert not any(s.get("example_cwe") == "CWE-094" for s in slots)
    assert slots[0]["title_terms"] == [" NosqlInjectionQuery API"]


@pytest.mark.parametrize(
    "requirement", ["Detect NoSQL injection", "Detect stored XSS", "Detect DOM XSS"]
)
def test_non_core_families_cannot_be_reported_as_stable_relational_or_reflected_templates(
    requirement,
):
    from app.adapters.codeql.grounded_spec import can_constrain

    assert not can_constrain(
        {
            "purpose": "vulnerability_detector",
            "strategy": "auto",
            "requirement": requirement,
        },
        strict_scope=True,
    )


def test_non_core_role_refinement_preserves_every_core_operation():
    from app.adapters.retrieval.role_queries import refined_slots, role_query

    for cwe in ("CWE-094", "CWE-089", "CWE-079"):
        for language in ("python", "javascript"):
            slots = [
                ("reference", 1, ["actual-declaration"], None),
                ("rule_example", 2, None, cwe),
            ]
            topic = ("core", cwe)
            assert refined_slots(language, topic, slots) == slots
            assert role_query(
                topic,
                ["ApiGraphs", "DataFlow", "TaintTracking"],
                "original requirement",
                "auto",
            ) == ("original requirement", "auto")


def test_api_creates_version8_rule_and_exposes_supported_generation_boundary(
    pipeline_context, monkeypatch
):
    from app.api.routes import stages

    monkeypatch.setattr(stages.execute_stage, "delay", lambda *_: None)
    client = pipeline_context["client"]
    caps = client.get("/api/v1/knowledge/capabilities").json()
    assert caps["prompt_version"] == "8"
    assert (
        caps["rule_generation"]["other_purposes_and_strategies"]
        == "experimental_free_ql_draft"
    )
    response = client.post(
        f"/api/v1/audits/{pipeline_context['run_id']}/rule",
        json={
            "requirement": "Detect Python eval code injection",
            "purpose": "vulnerability_detector",
            "source_paths": ["app.py"],
        },
    )
    assert response.status_code == 201
    assert response.json()["prompt_version"] == "8"
