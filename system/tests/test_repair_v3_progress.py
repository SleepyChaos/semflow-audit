"""Repair3 uses the production graph, exact source ranges and finite tool reuse."""

import pytest
from app.services.inspection_progress import existing_read
from app.workflows.repair import build_repair_graph

from tests.test_semantic_development import (
    InspectModel,
    RepairModel,
    ready,
    repair_service,
)


def test_read_at_eof_reuses_full_body_without_reading_again():
    material = {
        "id": "source",
        "kind": "code",
        "reference": {"file": "a.py", "start_line": 1, "end_line": 3},
    }
    call = {
        "name": "read_source",
        "arguments": {"file": "a.py", "start_line": 1, "end_line": 120},
    }
    assert existing_read(call, [material], [], file_lengths={"a.py": 3}) is material
    assert existing_read(call, [material], []) is None
    assert existing_read(call, [material], [], file_lengths={"a.py": 200}) is None


def test_repair_inspection_shows_actual_eof_and_reuses_oversized_request(
    pipeline_context,
):
    def respond(payload):
        assert payload["source_windows"][0]["complete_file"]
        if not payload["tool_trace"]:
            return {
                "action": "tool",
                "tool": {
                    "name": "read_source",
                    "arguments": {"file": "app.py", "start_line": 1, "end_line": 120},
                    "reason": "Need the remaining implementation",
                },
            }
        assert payload["tool_trace"][-1]["reused"]
        return ready(payload)

    service = repair_service(pipeline_context, InspectModel(respond))
    from app.services.repair_semantics import SemanticRepair

    repair = SemanticRepair(service)
    source = service.evidence.read("app.py", 1, 120)
    result = repair.reader.inspect([{"description": "eval risk"}], [source])
    assert result["view"]["action"] == "ready"
    assert not (service.directory / "semantics/tools.json").exists()


def test_api_default_repair3_generates_and_validates_isolated_patch(
    pipeline_context, monkeypatch
):
    import ast

    from app.jobs.stages import execute_stage
    from app.persistence.stage_repository import StageRepository
    from app.services import repair as module
    from app.services.repair import RepairService

    initial = repair_service(pipeline_context, RepairModel())
    initial.repository.update(
        initial.stage_id,
        status="cancelled",
        error="test setup complete; no active repair should block API",
    )
    monkeypatch.setattr(execute_stage, "delay", lambda *_: None)
    response = pipeline_context["client"].post(
        f"/api/v1/audits/{pipeline_context['run_id']}/repair",
        json=initial.inputs.model_dump(mode="json"),
    )
    assert response.status_code == 201
    stage = response.json()
    assert stage["prompt_version"] == "3"
    assert StageRepository().claim(stage["id"])

    class ContractModel(RepairModel):
        def generate(self, purpose, payload, schema):
            if payload.get("phase") == "assess_patch_contract":
                return schema.model_validate(
                    {
                        "constraints": [
                            {
                                "fact_index": i,
                                "status": "consistent",
                                "explanation": "Numeric input is preserved without dynamic evaluation",
                                "evidence_ids": [payload["evidence"][0]["id"]],
                            }
                            for i in payload["required_fact_indices"]
                        ],
                        "behavior_conflicts": [],
                        "limitation": "Scripted consistency response, not a real model assessment",
                    }
                )
            return super().generate(purpose, payload, schema)

    model = ContractModel()
    service = RepairService(stage["id"], model)

    def validate(workspace, *_):
        try:
            ast.parse((workspace / "app.py").read_text())
        except SyntaxError:
            return {"status": "failed", "output": "SyntaxError"}
        return {"status": "passed", "output": "parsed"}

    monkeypatch.setattr(module, "validate_workspace", validate)
    result = build_repair_graph(service).invoke({})
    assert result["passed"] and result["attempt"] == 2
    assert (
        service.directory / "attempt-2/workspace/app.py"
    ).read_text() == "value = int(input())\n"
    assert (service.evidence.root / "app.py").read_text() == "value = eval(input())\n"


def test_large_read_is_explicitly_paged_without_claiming_full_file(pipeline_context):
    from app.adapters.snapshot import snapshot_digest
    from app.core.db import engine
    from app.persistence.audit_models import AuditRun
    from app.services.inspection_tools import read_page
    from sqlmodel import Session

    service = repair_service(pipeline_context, InspectModel())
    (service.evidence.root / "app.py").write_text("x=1\n" * 300)
    with Session(engine) as db:
        audit = db.get(AuditRun, pipeline_context["run_id"])
        audit.snapshot_hash = snapshot_digest(service.evidence.root)
        db.add(audit)
        db.commit()
        db.refresh(audit)
        service.evidence.audit = audit
    data = read_page(
        service.evidence,
        "read_source",
        {"file": "app.py", "start_line": 1, "end_line": 300},
    )
    assert data["reference"]["end_line"] == 151
    assert len(data["content"].splitlines()) == 151
    assert data["read_adjustment"]["total_lines"] == 300
    assert data["read_adjustment"]["returned_end_line"] == 151


def test_invalid_search_arguments_are_correctable_without_trusting_tool_facts(
    pipeline_context,
):
    def respond(payload):
        if not payload.get("latest_tool_error"):
            return {
                "action": "tool",
                "tool": {
                    "name": "search_source",
                    "arguments": {"query": "eval"},
                    "reason": "Locate target operation",
                },
                "facts": [
                    {
                        "statement": "Unsupported provisional claim",
                        "state": "supported",
                        "evidence_ids": [],
                        "category": "implementation",
                    }
                ],
            }
        assert payload["latest_tool_error"]["status"] == "not_read"
        assert "text" in payload["tool_contract"]["search_source"]["arguments"]
        return ready(payload)

    service = repair_service(pipeline_context, InspectModel(respond))
    from app.services.repair_semantics import SemanticRepair

    reader = SemanticRepair(service).reader
    source = service.evidence.read("app.py", 1, 1)
    result = reader.inspect([{"description": "eval risk"}], [source])
    assert result["view"]["facts"][0]["evidence_ids"] == [source["id"]]
    assert not (service.directory / "semantics/tools.json").exists()


def test_repair_documents_are_lazy_and_request_intent_has_separate_evidence(
    pipeline_context,
):
    from app.services.repair_semantics import SemanticRepair

    observed = []

    def respond(payload):
        observed.append(payload)
        assert payload["repair_scope"]["writable_files"] == ["app.py"]
        assert any(r["kind"] == "repair_request" for r in payload["evidence"])
        assert not any(
            r["reference"].get("file") == "README.md" for r in payload["evidence"]
        )
        return ready(payload)

    service = repair_service(pipeline_context, InspectModel(respond))
    SemanticRepair(service).prepare({})
    assert observed


def test_request_intent_alone_cannot_establish_ready_source_facts(pipeline_context):
    import pytest
    from app.domain.audit import AuditError
    from app.services.repair_semantics import SemanticRepair

    def respond(payload):
        result = ready(payload)
        request = next(
            row for row in payload["evidence"] if row["kind"] == "repair_request"
        )
        for fact in result["facts"]:
            fact["evidence_ids"] = [request["id"]]
        return result

    service = repair_service(pipeline_context, InspectModel(respond))
    with pytest.raises(AuditError, match="缺少实际源码引用"):
        SemanticRepair(service).prepare({})


def test_read_coverage_unions_pages_without_hiding_holes():
    from app.services.inspection_progress import read_coverage

    windows = [
        {"file": "a.py", "total_lines": 308, "start_line": start, "end_line": end}
        for start, end in [(1, 36), (36, 186), (186, 308)]
    ]
    result = read_coverage(windows)
    assert result == [
        {
            "file": "a.py",
            "total_lines": 308,
            "fully_supplied": True,
            "unread_ranges": [],
        }
    ]
    result = read_coverage([windows[0], windows[2]])
    assert not result[0]["fully_supplied"]
    assert result[0]["unread_ranges"] == [{"start_line": 37, "end_line": 185}]


@pytest.mark.parametrize("conflict_kind", ["implementation", "understanding"])
def test_production_graph_retries_semantic_conflict_even_when_syntax_passes(
    pipeline_context, monkeypatch, conflict_kind
):
    import ast
    import json
    from uuid import UUID

    from app.core.db import engine
    from app.persistence.stage_models import StageRun
    from app.services import repair as module
    from app.services.repair import RepairService
    from sqlmodel import Session

    class ConflictModel(RepairModel):
        def generate(self, purpose, payload, schema):
            phase = payload["phase"]
            if phase == "inspect_semantics" and conflict_kind == "understanding":
                value = ready(payload)
                if self.proposals == 0:
                    value["modification_semantics"] = (
                        "Convert all numeric output to text for unrelated consumers"
                    )
                return schema.model_validate(value)
            if phase == "propose_patch":
                self.proposals += 1
                return schema.model_validate(
                    {
                        "changes": [
                            {
                                "file": "app.py",
                                "old_text": "eval(input())",
                                "new_text": "str(input())"
                                if self.proposals == 1
                                else "int(input())",
                                "reason": "Preserve conversion without evaluating input",
                            }
                        ],
                        "summary": "Replace dynamic evaluation with explicit conversion",
                    }
                )
            if phase == "assess_patch_contract":
                return schema.model_validate(
                    {
                        "constraints": [
                            {
                                "fact_index": 0,
                                "status": "conflicting"
                                if self.proposals == 1
                                and conflict_kind == "implementation"
                                else "consistent",
                                "explanation": "String conversion changes required numeric behavior"
                                if self.proposals == 1
                                else "Numeric conversion preserves the required behavior",
                                "evidence_ids": [payload["evidence"][0]["id"]],
                            }
                        ],
                        "behavior_conflicts": [],
                        "interpretation_conflicts": [
                            "Model interpretation expands a numeric conversion request to unrelated text consumers"
                        ]
                        if self.proposals == 1 and conflict_kind == "understanding"
                        else [],
                        "limitation": "Scripted assessment tests feedback routing only",
                    }
                )
            return super().generate(purpose, payload, schema)

    initial = repair_service(pipeline_context, ConflictModel())
    with Session(engine) as db:
        stage = db.get(StageRun, UUID(initial.stage_id))
        stage.prompt_version = "3"
        db.add(stage)
        db.commit()
    service = RepairService(initial.stage_id, initial.provider)

    def syntax(workspace, *_):
        ast.parse((workspace / "app.py").read_text())
        return {"status": "passed", "output": "Valid syntax"}

    monkeypatch.setattr(module, "validate_workspace", syntax)
    result = build_repair_graph(service).invoke({})
    assert result["passed"] and result["attempt"] == 2
    assert (service.directory / "semantics/retry-1/result.json").exists() == (
        conflict_kind == "understanding"
    )
    checks = json.loads((service.directory / "attempt-1/checks.json").read_text())
    assert checks["isolated_tests"]["status"] == "passed"
    assert checks["semantic_contract"]["status"] == "failed"
    assert (
        service.directory / "attempt-2/workspace/app.py"
    ).read_text() == "value = int(input())\n"
    assert (service.evidence.root / "app.py").read_text() == "value = eval(input())\n"


def test_unread_repository_fact_gets_one_bounded_clarification(pipeline_context):
    from app.services.repair_semantics import SemanticRepair

    def respond(payload):
        feedback = payload["feedback"]["validation_feedback"]
        if not feedback:
            value = ready(payload)
            value["action"] = "insufficient"
            value["facts"] = [
                {
                    "statement": "An implementation detail remains unread",
                    "state": "unknown",
                    "category": "implementation",
                    "critical": True,
                    "evidence_ids": [],
                }
            ]
            return value
        assert "unresolved_source_facts" in feedback
        return ready(payload)

    service = repair_service(pipeline_context, InspectModel(respond))
    result = SemanticRepair(service).prepare({})
    assert result["context_hash"]
    assert service.provider.usage["calls"] == 2


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "value = eval(input())\n" + "# padding\n" * 80}],
    indirect=True,
)
def test_affected_caller_reads_reach_new_understanding_and_authorized_windows(
    pipeline_context,
):
    import json

    from app.services.repair_semantics import SemanticRepair

    model = InspectModel()
    service = repair_service(pipeline_context, model)
    repair = SemanticRepair(service)
    state = repair.prepare({})
    caller = service.evidence.read("app.py", 50, 60)
    state.update(
        attempt=1,
        diagnosis={
            "category": "understanding",
            "summary": "Read the actual affected call site",
        },
        checks={
            "semantic_contract": {
                "caller_impact": {"obligations": [{"evidence_id": caller["id"]}]}
            }
        },
    )
    next_state = repair.refresh_understanding(state)
    assert next_state["context_hash"] != state["context_hash"]
    context = json.loads((service.directory / "repair-context.json").read_text())
    assert any(
        row["id"] == caller["id"] and row["content"] == caller["content"]
        for row in context["inspection"]["evidence"]
    )
    assert any(
        row["start_line"] == 50 and row["end_line"] == 60
        for row in context["file_views"]["app.py"]["segments"]
    )
    assert (service.directory / "context-before-1.json").exists()
    assert (
        service.evidence.root.joinpath("app.py").read_text()
        == "value = eval(input())\n" + "# padding\n" * 80
    )
