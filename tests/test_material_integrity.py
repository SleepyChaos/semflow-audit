"""Material completeness, stale identity and original-project gate behavior."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.adapters.retrieval.chunking import source_chunks
from app.adapters.retrieval.knowledge import KnowledgeRetriever, import_knowledge
from app.domain.audit import AuditError
from app.services.context_materials import digest, semantic_policy
from app.services.repair_semantics import SemanticRepair
from app.services.rule_project_validation import root_candidates
from app.services.rules import RuleService
from app.workflows.rules import build_rule_graph

from tests.test_rule_synthesis import draft


def test_rule_metadata_adaptation_preserves_logic_and_rejects_unloaded_models(tmp_path):
    from app.services.rule_output import assign_namespace, verify_module_imports

    response = draft(str(uuid4()))
    body = 'import python\nfrom Call c select c, "candidate"'
    response.query = "/** @id py/original */\n" + body
    adapted = assign_namespace(response, tmp_path)
    assert adapted.query.endswith(body)
    assert "@id audit/generated-" in adapted.query
    assert (
        json.loads((tmp_path / "model-candidate.json").read_text())["query"]
        == response.query
    )
    adapted.modules = {"Unused.qll": "import python"}
    with pytest.raises(AuditError, match="未被查询导入"):
        verify_module_imports(adapted)
    adapted.query += "\nimport Unused\n"
    verify_module_imports(adapted)


def test_original_database_needs_exact_target_source_archive(tmp_path):
    from zipfile import ZipFile

    import yaml
    from app.services.rule_database_identity import verify_database

    root, database = tmp_path / "source", tmp_path / "database"
    root.mkdir()
    database.mkdir()
    (root / "a.py").write_text("eval(input())\n")
    audit = SimpleNamespace(language="python", codeql_version="fixed-v1")
    (database / "codeql-database.yml").write_text(
        yaml.safe_dump(
            {
                "sourceLocationPrefix": str(root),
                "primaryLanguage": "python",
                "creationMetadata": {"cliVersion": "fixed-v1"},
                "finalised": True,
            }
        )
    )
    with ZipFile(database / "src.zip", "w") as source:
        source.writestr(str(root / "a.py").lstrip("/"), "eval(input())\n")
    assert verify_database(database, root, audit, ["a.py"])["files"]
    (root / "a.py").write_text("int(input())\n")
    with pytest.raises(AuditError, match="完整归档"):
        verify_database(database, root, audit, ["a.py"])


def test_known_operation_routes_to_matching_api_and_examples(pipeline_context):
    from app.adapters.retrieval.dual_corpus import retrieve_both

    for title in (
        "CodeInjectionQuery",
        "CodeInjectionCustomizations",
        "ApiGraphs",
        "PathInjectionQuery",
    ):
        import_knowledge(
            pipeline_context["owner"],
            title,
            "routing:" + title,
            "python",
            "eval " + title + " exact unique API declaration",
            {"api_version": "routing-v1"},
            corpus="reference",
        )
    for cwe in ("CWE-094", "CWE-022"):
        import_knowledge(
            pipeline_context["owner"],
            cwe,
            "routing:" + cwe,
            "python",
            "eval unique development test query " + cwe,
            {
                "api_version": "routing-v1",
                "cwe": cwe,
                "validation": {"status": "passed"},
            },
            corpus="rule_example",
        )
    rows = retrieve_both(
        pipeline_context["owner"],
        "python",
        "eval code injection",
        "routing-v1",
        mode="bm25",
    )
    assert {r["title"] for r in rows if r["corpus"] == "reference"} >= {
        "CodeInjectionQuery",
        "CodeInjectionCustomizations",
    }
    assert all(r["title"] != "PathInjectionQuery" for r in rows)
    assert all(
        r["provenance"]["cwe"] == "CWE-094"
        for r in rows
        if r["corpus"] == "rule_example"
    )


from tests.test_semantic_development import (
    InspectModel,
    RepairModel,
    make_stage,
    ready,
    repair_service,
)


def test_api_source_windows_preserve_original_lines_without_markdown_parsing():
    content = "  /** ```ql\n" + "predicate p() { result = 1 }\n" * 600 + "``` */\n"
    chunks = source_chunks(content)
    assert "".join(chunks) == content and len(chunks) > 1
    assert all(len(c) <= 8000 for c in chunks)
    assert all(c.endswith("\n") for c in chunks)


def test_frozen_semantic_budget_survives_config_change(tmp_path, monkeypatch):
    from app.core.audit_config import audit_settings

    first = semantic_policy(tmp_path)
    monkeypatch.setattr(audit_settings, "REPAIR_ATTEMPTS", 9)
    assert semantic_policy(tmp_path) == first


def test_failed_official_examples_are_excluded_from_generation_retrieval(
    pipeline_context,
):
    for state in ("passed", "failed"):
        import_knowledge(
            pipeline_context["owner"],
            state,
            state,
            "python",
            "distinct_official_marker eval source sink API",
            {"api_version": "v", "validation": {"status": state}},
            corpus="rule_example",
        )
    rows = KnowledgeRetriever().retrieve(
        pipeline_context["owner"],
        "python",
        "distinct_official_marker",
        api_version="v",
        corpus="rule_example",
        mode="bm25",
    )
    assert rows and all(r["title"] == "passed" for r in rows)


def test_repair_saved_validation_cannot_be_reused_for_changed_workspace(
    pipeline_context, monkeypatch
):
    import app.services.repair as module

    provider = RepairModel()
    provider.proposals = 1
    service = repair_service(pipeline_context, provider)
    monkeypatch.setattr(module, "validate_workspace", lambda *_: {"status": "passed"})
    repair = SemanticRepair(service)
    state = repair.prepare({})
    state.update(repair.propose(state))
    state.update(repair.apply(state))
    repair.validate(state)
    (service.directory / "attempt-1/workspace/app.py").write_text(
        "value = eval(input())\n"
    )
    with pytest.raises(AuditError, match="已变化"):
        repair.validate(state)


def test_location_or_new_id_alone_does_not_establish_root_match():
    target = SimpleNamespace(weakness="CWE-94", location={"file": "a.py", "line": 4})
    matching = {
        "id": "new",
        "tags": ["external/cwe/cwe-094"],
        "locations": [{"file": "a.py", "line": 4}],
    }
    wrong_cwe = {**matching, "tags": ["external/cwe/cwe-089"]}
    wrong_file = {**matching, "locations": [{"file": "b.py", "line": 4}]}
    assert root_candidates([wrong_cwe, wrong_file, matching], target) == [matching]
    assert (
        root_candidates(
            [matching], SimpleNamespace(weakness="unknown", location=target.location)
        )
        == []
    )


def test_v6_three_inputs_and_project_replay_precede_approval(
    pipeline_context, monkeypatch
):
    import app.services.rule_materials as materials
    import app.services.rule_project_validation as replay
    import app.services.rule_synthesis as synthesis
    from langgraph.checkpoint.memory import InMemorySaver

    identifiers = [str(uuid4()), str(uuid4())]
    knowledge = [
        {
            "id": identifiers[i],
            "corpus": corpus,
            "content": "fixed eval API",
            "digest": digest(corpus),
        }
        for i, corpus in enumerate(("reference", "rule_example"))
    ]
    monkeypatch.setattr(materials, "retrieve_both", lambda *_args, **_kwargs: knowledge)
    provider = InspectModel()

    def reply(payload):
        if payload["phase"] == "inspect_semantics":
            return ready(payload)
        assert {r["corpus"] for r in payload["knowledge"]} == {
            "reference",
            "rule_example",
        }
        assert (
            "eval(input())" in payload["semantic_inspection"]["evidence"][0]["content"]
        )
        assert payload["confirmed_target"]["description"]
        value = draft(identifiers[0]).model_dump(mode="json")
        value["purpose"] = "review_anchor"
        value["query"] = (
            '/** @id audit/unit-test\n * @name test\n * @description test\n * @kind problem\n * @problem.severity warning\n * @precision low\n */\nimport python\nfrom Call c select c, "call"\n'
        )
        return value

    provider.callback = reply
    stage = make_stage(
        pipeline_context,
        "rule",
        "6",
        {
            "requirement": "Inventory eval operations with real code",
            "source_paths": ["app.py"],
        },
    )
    service = RuleService(stage, provider)
    monkeypatch.setattr(synthesis, "compile_query", lambda *_: None)
    events = []
    monkeypatch.setattr(
        synthesis,
        "validate_fixtures",
        lambda *_: events.append("development") or {"status": "passed"},
    )
    monkeypatch.setattr(
        replay,
        "replay_project",
        lambda *_: events.append("project") or {"status": "not_evaluated"},
    )
    result = build_rule_graph(service, InMemorySaver()).invoke(
        {}, {"configurable": {"thread_id": stage}}
    )
    assert result["__interrupt__"] and events == ["development", "project"]
    assert provider.usage["calls"] == 2
    assert "query" not in result and result["materials_digest"]
    path = service.directory / "rule-materials.json"
    bundle = json.loads(path.read_text())
    bundle["target"]["description"] = "tampered"
    path.write_text(json.dumps(bundle))
    with pytest.raises(AuditError, match="材料被修改"):
        synthesis.RuleSynthesis(service)._context(result)
