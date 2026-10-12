"""Recovery must preserve material identity, tool results and finite retry budgets."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.adapters.snapshot import snapshot_digest
from app.domain.audit import AuditError
from app.services.context_materials import semantic_policy
from app.services.rule_development import execute_development
from app.services.rule_project_validation import check_project_validation
from app.services.rules import RuleService
from app.workflows.repair import build_repair_graph

from tests.test_rule_synthesis import draft
from tests.test_semantic_development import (
    InspectModel,
    RepairModel,
    make_stage,
    repair_service,
)


def test_completed_development_replays_once_and_rejects_changed_fixture(tmp_path):
    service = SimpleNamespace(
        directory=tmp_path, audit=SimpleNamespace(language="python")
    )
    pack = tmp_path / "pack"
    pack.mkdir()
    response = draft(str(uuid4()))
    calls = []

    def runner(directory, *_):
        calls.append(directory)
        source = directory / "positive"
        source.mkdir(parents=True)
        (source / "app.py").write_text("eval(input())\n")
        return {
            "status": "passed",
            "tests": {"positive": {"snapshot_hash": snapshot_digest(source)}},
        }

    first = execute_development(service, pack, response, {}, 1, runner)
    assert execute_development(service, pack, response, {}, 1, runner) == first
    assert len(calls) == 1
    (calls[0] / "positive/app.py").write_text("int(input())\n")
    with pytest.raises(AuditError, match="源码被修改"):
        execute_development(service, pack, response, {}, 1, runner)
    assert len(calls) == 1


def test_prepared_rule_reuses_frozen_rag_and_rejects_input_change(
    pipeline_context, monkeypatch
):
    import app.services.rule_materials as materials

    calls = []

    def retrieve(*args, **kwargs):
        calls.append(kwargs)
        return [
            {"id": str(uuid4()), "corpus": corpus, "content": "fixed eval API"}
            for corpus in ("reference", "rule_example")
        ]

    monkeypatch.setattr(materials, "retrieve_both", retrieve)
    stage = make_stage(
        pipeline_context,
        "rule",
        "6",
        {"requirement": "Inventory eval", "source_paths": ["app.py"]},
    )
    model = InspectModel()
    service = RuleService(stage, model)
    first = service.retrieve()
    assert service.retrieve() == first
    assert len(calls) == model.usage["calls"] == 1
    service.inputs.requirement = "Different target"
    with pytest.raises(AuditError, match="输入配置已变化"):
        service.retrieve()
    assert len(calls) == 1


def test_stage_budget_cannot_be_expanded_by_editing_artifact(pipeline_context):
    service = repair_service(pipeline_context, RepairModel())
    policy = semantic_policy(service.directory)
    path = service.directory / "semantic-policy.json"
    path.write_text(json.dumps({**policy, "repair_attempts": 100}))
    with pytest.raises(AuditError, match="预算配置产物被修改"):
        semantic_policy(service.directory)


def test_failed_repairs_stop_at_three_candidates_and_keep_original(
    pipeline_context, monkeypatch
):
    import app.services.repair as module

    model = RepairModel()
    service = repair_service(pipeline_context, model)
    monkeypatch.setattr(
        module,
        "validate_workspace",
        lambda *_: {"status": "failed", "output": "SyntaxError: candidate rejected"},
    )
    result = build_repair_graph(service).invoke({})
    assert result["attempt"] == model.proposals == 3 and not result["passed"]
    assert service.repository.get(service.stage_id).result["status"] == "needs_review"
    assert (service.evidence.root / "app.py").read_text() == "value = eval(input())\n"
    assert all(
        (service.directory / f"attempt-{i}/checks.json").is_file() for i in (1, 2, 3)
    )


def test_older_replay_receipt_cannot_bypass_new_publish_identity_gate():
    rule = SimpleNamespace(validation={"project_replay": {"status": "not_evaluated"}})
    with pytest.raises(AuditError, match="身份不完整"):
        check_project_validation(rule)


def test_frozen_retrieval_scope_excludes_later_documents(pipeline_context):
    from uuid import UUID

    from app.adapters.retrieval.knowledge import KnowledgeRetriever, import_knowledge

    owner = pipeline_context["owner"]
    frozen = import_knowledge(
        owner,
        "original",
        "frozen",
        "python",
        "freeze_scope_unique eval",
        corpus="reference",
    )
    import_knowledge(
        owner,
        "later",
        "newer",
        "python",
        "freeze_scope_unique eval",
        corpus="reference",
    )
    retriever = KnowledgeRetriever()
    rows = retriever.retrieve(
        owner,
        "python",
        "freeze_scope_unique",
        mode="bm25",
        document_ids=[UUID(frozen["document_id"])],
    )
    assert rows and {r["title"] for r in rows} == {"original"}
    assert not retriever.retrieve(
        owner, "python", "freeze_scope_unique", mode="bm25", document_ids=[]
    )
