"""Platform review calls the same unified research graph with frozen real evidence."""

from app.main import app
from app.persistence.stage_models import Candidate
from app.research_bridge.models import ResearchBinding
from app.research_bridge.requests import research_root
from app.runtime.scans import run_scan
from app.runtime.stages import run_stage
from app.services.stage_lifecycle import create_stage_run
from fastapi.testclient import TestClient
from semflow_research.public.discovery_results import read_result
from sqlmodel import Session, select

from tests.research_bridge_cases import upload


class ReviewModel:
    model = "explicit-review-substitute"

    def __init__(self):
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        self.contexts = []

    def generate(self, purpose, payload, schema):
        assert purpose == "review"
        self.contexts.append(payload)
        self.usage["calls"] += 1
        return schema.model_validate(
            {
                "action": "final",
                "summary": "Source read, caller trust is unresolved",
                "candidate_assessments": [
                    {
                        "candidate_id": row["candidate_id"],
                        "assessment": "insufficient",
                        "weakness": "CWE-95",
                        "reason": "Source proves evaluation but caller trust is unknown",
                        "evidence_ids": row["evidence_ids"],
                        "missing_premises": ["Caller trust is unknown"],
                    }
                    for row in payload["targets"]
                ],
                "new_findings": [],
                "anchor_assessments": [],
                "root_relations": [],
            }
        )


def test_new_review_runs_kernel_and_preserves_static_identity_and_human_gate(
    bridge_case, scanner
):
    db, owner, _, _ = bridge_case
    audit = upload(bridge_case)
    assert run_scan(str(audit.id)).status == "completed"
    with Session(db) as session:
        stage = create_stage_run(
            session,
            audit.id,
            owner,
            "review",
            {"max_steps": 1, "supplement_insufficient": False},
            prompt_version="4",
        )
    model = ReviewModel()
    final = run_stage(str(stage.id), kernel_model_factory=lambda: model)
    assert final.status == "completed", final.error
    assert model.usage["calls"] == 1
    with Session(db) as session:
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == stage.id)
        ).one()
        rows = session.exec(
            select(Candidate).where(Candidate.stage_id == stage.id)
        ).all()
        assert len(rows) == 1 and rows[0].model_assessment == "insufficient"
        assert rows[0].status == "pending" and rows[0].static_finding_id
        native = read_result(binding.execution_id, root=research_root())
        assert len(native.candidates) == 1
        assert native.assessments[0].conclusion == "insufficient"
        assert native.candidates[0].static_finding_ref
    run_stage(str(stage.id), kernel_model_factory=lambda: model)
    assert model.usage["calls"] == 1
    with TestClient(app) as client:
        result = client.get(f"/api/v1/audits/{audit.id}/candidates")
        assert result.status_code == 200, result.text
        assert result.json()[0]["model_assessment"] == "insufficient"
        assert result.json()[0]["status"] == "pending"


def test_current_review_method_keeps_uncertain_verdict_and_materials_api(
    bridge_case, scanner
):
    from semflow_contracts.modelio.unified_review import UnifiedReviewResponse

    class CurrentReviewModel(ReviewModel):
        def generate(self, purpose, payload, schema):
            body = (
                super()
                .generate(purpose, payload, UnifiedReviewResponse)
                .model_dump(mode="json")
            )
            for row in body["candidate_assessments"]:
                row.update(
                    reason="源码存在动态执行，但调用方输入的信任边界尚未核实。",
                    missing_premises=["调用方的信任边界尚未核实"],
                    security_property=next(
                        target["security_property"]
                        for target in payload["targets"]
                        if target["candidate_id"] == row["candidate_id"]
                    ),
                )
                row["premises"] = [
                    {
                        "premise": name,
                        "status": "missing",
                        "reason": "当前源码证据不足以建立此项必要前提。",
                        "evidence_ids": [],
                    }
                    for name in ("operation", "input_or_policy", "unsafe_protection")
                ]
                row["detail"] = {
                    "title": "动态执行操作",
                    "description": "本项目源码中可观察到动态执行操作，尚待核实调用方。",
                    "impact": "如果输入可由攻击者控制，可能执行非预期的代码。",
                    "evidence_ids": row["evidence_ids"],
                    "exploitation": {
                        "status": "missing_preconditions",
                        "expected_result": "由于信任边界未知，本轮没有实际执行利用验证。",
                        "evidence_ids": [],
                    },
                }
            return schema.model_validate(body)

    db, owner, _, _ = bridge_case
    audit = upload(bridge_case)
    assert run_scan(str(audit.id)).status == "completed"
    with Session(db) as session:
        stage = create_stage_run(
            session,
            audit.id,
            owner,
            "review",
            {"max_steps": 1, "supplement_insufficient": False},
        )
        assert stage.prompt_version == "12"
    model = CurrentReviewModel()
    result = run_stage(str(stage.id), kernel_model_factory=lambda: model)
    assert result.status == "completed", result.error
    with Session(db) as session:
        row = session.exec(
            select(Candidate).where(Candidate.stage_id == stage.id)
        ).one()
        assert row.model_assessment == "insufficient" and row.status == "pending"
    with TestClient(app) as client:
        materials = client.get(f"/api/v1/stages/{stage.id}/materials")
        assert materials.status_code == 200, materials.text
        assert materials.json()["entries"][0]["candidate_id"] == str(row.id)
        assert (
            client.get(f"/api/v1/audits/{audit.id}/candidates").json()[0]["status"]
            == "pending"
        )


def test_dual_discovery_and_platform_review_preserve_both_inputs_and_scout_provenance(
    bridge_case, scanner
):
    from tests.research_bridge_cases import CurrentScoutModel

    db, owner, _, _ = bridge_case
    audit = upload(bridge_case, dual=True)
    scanned = run_scan(str(audit.id), model=CurrentScoutModel())
    assert scanned.status == "completed", scanned.error
    assert scanned.coverage["dual_engine"]["scout"]["status"] == "completed"
    with Session(db) as session:
        original = session.exec(
            select(Candidate).where(Candidate.audit_id == audit.id)
        ).one()
        original_id = original.id
        stage = create_stage_run(
            session,
            audit.id,
            owner,
            "review",
            {"max_steps": 1, "batch_size": 4, "supplement_insufficient": False},
            prompt_version="4",
        )
    model = ReviewModel()
    final = run_stage(str(stage.id), kernel_model_factory=lambda: model)
    assert final.status == "completed", final.error
    assert len(model.contexts[0]["targets"]) == 2
    source_target = next(
        target for target in model.contexts[0]["targets"] if target["origin"] == "scout"
    )
    assert "trust boundary" in source_target["hypothesis"]["missing_premises"][0]
    with Session(db) as session:
        rows = session.exec(
            select(Candidate).where(Candidate.stage_id == stage.id)
        ).all()
        assert len(rows) == 2
        scout = next(row for row in rows if row.origin == "ai")
        assert scout.related_target == str(original_id)
        assert all(
            row.model_assessment == "insufficient" and row.status == "pending"
            for row in rows
        )
