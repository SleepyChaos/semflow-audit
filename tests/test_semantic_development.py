"""Behavioral checks. Scripted models prove orchestration, not LLM quality."""

import json
from uuid import UUID, uuid4

import pytest
from app.adapters.artifacts import ArtifactStore
from app.adapters.retrieval.knowledge import KnowledgeRetriever, import_knowledge
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.stage_models import Candidate, StageRun
from app.persistence.stage_repository import StageRepository
from app.services.evidence import EvidenceService
from app.services.repair import RepairService
from app.services.semantic_inspection import SemanticInspection
from app.workflows.repair import build_repair_graph
from sqlmodel import Session


def make_stage(ctx, kind="repair", version="2", inputs=None):
    with Session(engine) as db:
        stage = StageRun(
            audit_id=ctx["run_id"],
            kind=kind,
            prompt_version=version,
            inputs=inputs or {},
        )
        db.add(stage)
        db.commit()
        db.refresh(stage)
        identifier = str(stage.id)
    StageRepository().claim(identifier)
    return identifier


def ready(payload):
    return {
        "action": "ready",
        "project_overview": "A numeric conversion application",
        "target_flow": "External text enters conversion and is returned to the caller",
        "modification_semantics": "Preserve numeric conversion; prevent dynamic evaluation",
        "facts": [
            {
                "statement": "The target file interprets external input with eval",
                "state": "supported",
                "evidence_ids": [payload["evidence"][0]["id"]],
                "category": "security",
                "critical": True,
            }
        ],
    }


class InspectModel:
    model = "scripted-only"

    def __init__(self, callback=ready):
        self.callback, self.usage = callback, {"calls": 0}
        self.seen = []

    def generate(self, purpose, payload, schema):
        self.usage["calls"] += 1
        self.seen.append(payload)
        return schema.model_validate(self.callback(payload))


def inspector(ctx, provider):
    identifier = make_stage(ctx)
    evidence = EvidenceService(str(ctx["run_id"]), identifier, [])
    source = evidence.read("app.py", 1, 1)
    directory = ArtifactStore().directory(identifier)
    return SemanticInspection(
        evidence, provider, directory, StageRepository(), "repair"
    ), source


def test_semantic_calls_replay_without_second_model_request(pipeline_context):
    provider = InspectModel()
    service, source = inspector(pipeline_context, provider)
    first = service.inspect([{"description": "eval risk"}], [source])
    assert service.inspect([{"description": "eval risk"}], [source]) == first
    assert provider.usage["calls"] == 1
    assert first["view"]["facts"][0]["evidence_ids"] == [source["id"]]
    receipt = service.directory / "semantics/initial/step-0/receipt.json"
    value = json.loads(receipt.read_text())
    value["output"]["target_flow"] = "tampered"
    receipt.write_text(json.dumps(value))
    with pytest.raises(AuditError, match="产物身份"):
        service.inspect([{"description": "eval risk"}], [source])


@pytest.mark.parametrize("case", ["invented", "uncited", "unknown"])
def test_semantic_ready_requires_citations_and_no_critical_unknown(
    pipeline_context, case
):
    def reply(payload):
        value = ready(payload)
        fact = value["facts"][0]
        if case == "invented":
            fact["evidence_ids"] = [str(uuid4())]
        if case == "uncited":
            fact["evidence_ids"] = []
        if case == "unknown":
            fact["state"] = "unknown"
        return value

    service, source = inspector(pipeline_context, InspectModel(reply))
    with pytest.raises(AuditError):
        service.inspect([{"description": "risk"}], [source])


def test_inspection_can_read_related_source_without_granting_writes(pipeline_context):
    root = ArtifactStore().source(str(pipeline_context["run_id"]))
    # Synthetic source must be frozen before constructing the EvidenceService.
    (root / "helper.py").write_text("def convert(value):\n    return int(value)\n")
    from app.adapters.snapshot import snapshot_digest
    from app.persistence.audit_models import AuditRun

    with Session(engine) as db:
        audit = db.get(AuditRun, pipeline_context["run_id"])
        audit.snapshot_hash = snapshot_digest(root)
        db.add(audit)
        db.commit()

    def reply(payload):
        if not payload["tool_trace"]:
            return {
                "action": "tool",
                "tool": {
                    "name": "read_source",
                    "arguments": {"file": "helper.py", "start_line": 1, "end_line": 2},
                    "reason": "Read conversion semantics",
                },
            }
        value = ready(payload)
        value["facts"][0]["evidence_ids"] = [payload["evidence"][-1]["id"]]
        return value

    provider = InspectModel(reply)
    service, source = inspector(pipeline_context, provider)
    result = service.inspect([{"description": "risk"}], [source])
    assert service.inspect([{"description": "risk"}], [source]) == result
    assert provider.usage["calls"] == 2
    assert any(m["reference"].get("file") == "helper.py" for m in result["evidence"])
    with pytest.raises(AuditError):
        service.read_tool({"name": "read_source", "arguments": {"file": "../outside"}})


def test_dual_corpus_filters_do_not_cross_owner_or_version(pipeline_context):
    owner = pipeline_context["owner"]
    for corpus in ("reference", "rule_example"):
        import_knowledge(
            owner,
            corpus,
            "test:" + corpus,
            "python",
            "unique_dual_marker exact fixed API semantics",
            {"api_version": "fixture-v1"},
            corpus=corpus,
        )
    records = KnowledgeRetriever().retrieve(
        owner,
        "python",
        "unique_dual_marker",
        corpus="reference",
        api_version="fixture-v1",
        mode="bm25",
    )
    assert records and all(r["corpus"] == "reference" for r in records)
    assert not KnowledgeRetriever().retrieve(
        owner,
        "python",
        "unique_dual_marker",
        corpus="reference",
        api_version="fixture-v2",
        mode="bm25",
    )
    assert not KnowledgeRetriever().retrieve(
        uuid4(),
        "python",
        "unique_dual_marker",
        corpus="reference",
        api_version="fixture-v1",
        mode="bm25",
    )


def repair_service(ctx, model):
    source_stage = make_stage(ctx, "manual_evidence", "1")
    evidence = EvidenceService(str(ctx["run_id"]), source_stage, []).read(
        "app.py", 1, 1
    )
    with Session(engine) as db:
        candidate = Candidate(
            audit_id=ctx["run_id"],
            stage_id=UUID(source_stage),
            origin="test",
            title="Confirmed eval risk",
            description="Input is meant to be numeric; dynamic evaluation violates the conversion contract.",
            status="confirmed",
            evidence_ids=[evidence["id"]],
            location={"file": "app.py", "line": 1},
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        identifier = candidate.id
    stage = make_stage(
        ctx,
        inputs={
            "candidate_ids": [str(identifier)],
            "allowed_paths": ["app.py"],
            "rescan": False,
        },
    )
    return RepairService(stage, model)


class RepairModel(InspectModel):
    def __init__(self):
        super().__init__()
        self.proposals = 0

    def generate(self, purpose, payload, schema):
        if payload["phase"] == "inspect_semantics":
            return super().generate(purpose, payload, schema)
        self.usage["calls"] += 1
        self.seen.append(payload)
        if payload["phase"] == "diagnose_failure":
            return schema.model_validate(
                {
                    "category": "implementation",
                    "summary": "The first replacement has invalid syntax",
                    "next_action": "Use explicit numeric conversion",
                }
            )
        self.proposals += 1
        return schema.model_validate(
            {
                "changes": [
                    {
                        "file": "app.py",
                        "old_text": "eval(input())",
                        "new_text": "int(" if self.proposals == 1 else "int(input())",
                        "reason": "Preserve numeric conversion without evaluation",
                    }
                ],
                "summary": "Replace dynamic evaluation while preserving conversion",
            }
        )


def test_semantic_repair_retries_from_original_and_preserves_history(
    pipeline_context, monkeypatch
):
    provider = RepairModel()
    service = repair_service(pipeline_context, provider)
    from app.services import repair

    def checks(workspace, *_):
        text = (workspace / "app.py").read_text()
        return {
            "status": "failed" if "int(\n" in text else "passed",
            "output": "SyntaxError" if "int(\n" in text else "ok",
        }

    monkeypatch.setattr(repair, "validate_workspace", checks)
    result = build_repair_graph(service).invoke({})
    assert result["saved"] and result["attempt"] == 2
    assert result["passed"]
    assert (service.evidence.root / "app.py").read_text() == "value = eval(input())\n"
    assert (service.directory / "attempt-1/checks.json").is_file()
    assert (
        service.directory / "attempt-2/workspace/app.py"
    ).read_text() == "value = int(input())\n"
    assert provider.seen[-1]["previous_candidate"]["changes"][0]["new_text"] == "int("
    assert "failure_feedback" in provider.seen[-1]
    assert service.repository.get(service.stage_id).result["status"] == "checks_passed"


def test_environment_failure_does_not_trigger_code_rewrites(
    pipeline_context, monkeypatch
):
    provider = RepairModel()
    provider.proposals = 1
    service = repair_service(pipeline_context, provider)
    from app.services import repair

    def unavailable(*_):
        raise AuditError("Docker 验证环境不可用")

    monkeypatch.setattr(repair, "validate_workspace", unavailable)
    result = build_repair_graph(service).invoke({})
    assert result["attempt"] == 1 and not result["passed"]
    assert result["diagnosis"]["category"] == "environment"
    assert provider.proposals == 2
    assert service.repository.get(service.stage_id).result["status"] == "needs_review"


def test_new_rule_cannot_generate_without_real_source(pipeline_context):
    from app.services.rules import RuleService

    stage = make_stage(
        pipeline_context,
        "rule",
        "6",
        {"requirement": "Detect input reaching eval", "purpose": "review_anchor"},
    )
    with pytest.raises(AuditError, match="源码正文"):
        RuleService(stage, InspectModel()).retrieve()


def test_inspection_stage_cannot_read_other_audit(pipeline_context):
    with pytest.raises(AuditError, match="取证阶段"):
        EvidenceService(str(pipeline_context["run_id"]), str(uuid4()), [])
