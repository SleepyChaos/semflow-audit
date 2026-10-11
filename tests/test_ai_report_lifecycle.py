from uuid import UUID

import pytest
from app.api.routes import stages
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, StageRun
from app.persistence.stage_repository import StageRepository
from app.services.evidence import EvidenceService
from app.services.report_generation import ReportService
from app.workflows.report import build_report_graph
from sqlmodel import Session


class NarrativeProvider:
    model = "test-double-not-real-model"

    def __init__(self):
        self.usage = {"calls": 1}

    def generate(self, purpose, source, schema):
        assert purpose == "report"
        return schema.model_validate(
            {
                "overview": f"项目 {source['audit']['project_name']} 有待确认候选，需要核对实际证据。",
                "issues": [
                    {
                        "candidate_id": row["id"],
                        "title": "输入执行逻辑需要复核",
                        "explanation": "源码使用输入参与动态执行，具体可达性需要结合证据判断。",
                        "impact": "不可信输入若能到达执行操作，可能改变程序行为。",
                        "fix_suggestions": [
                            "根据真实业务需求替换动态执行，保留正常输入处理。"
                        ],
                        "verification_suggestions": [
                            "分别运行正常输入和攻击输入，检查安全与功能预期。"
                        ],
                        "evidence_ids": row["evidence_ids"],
                    }
                    for row in source["candidates"]
                ],
                "repair_review": "尚无修复和执行验证，不能声称漏洞已修好。",
                "limitations": ["报告是模型说明，不改变人工判断。"],
                "next_steps": ["核对源码并记录人工判断，再进行修复与验证。"],
            }
        )


@pytest.mark.parametrize("project_name", ["不同项目甲", "不同项目乙"])
def test_each_task_gets_ai_narrative_and_changed_decision_invalidates_it(
    pipeline_context, monkeypatch, project_name
):
    context = pipeline_context
    monkeypatch.setattr(audit_settings, "AI_MODEL", "test-only")
    monkeypatch.setattr(audit_settings, "AI_API_KEY", "")
    monkeypatch.setattr(
        audit_settings, "AI_BASE_URL", "http://local-provider.invalid/v1"
    )
    monkeypatch.setattr(stages.execute_stage, "delay", lambda *args: None)
    audit_id = context["run_id"]
    with Session(engine) as session:
        audit = session.get(AuditRun, audit_id)
        audit.project_name = project_name
        manual = StageRun(audit_id=audit_id, kind="manual_evidence", status="completed")
        session.add(audit)
        session.add(manual)
        session.commit()
        manual_id = manual.id
    evidence = EvidenceService(str(audit_id), str(manual_id), []).read("app.py", 1, 1)
    with Session(engine) as session:
        candidate = Candidate(
            audit_id=audit_id,
            stage_id=manual_id,
            origin="ai",
            title="English candidate",
            description="Potential eval risk",
            weakness="CWE-94",
            location={"file": "app.py", "line": 1},
            evidence_ids=[evidence["id"]],
        )
        session.add(candidate)
        session.commit()
        candidate_id = candidate.id
    client = context["client"]
    assert client.get(f"/api/v1/audits/{audit_id}/report.md").status_code == 409
    created = client.post(
        f"/api/v1/audits/{audit_id}/report-analysis", json={"force": False}
    )
    assert created.status_code == 200
    stage_id = created.json()["id"]
    assert StageRepository().claim(stage_id)
    service = ReportService(stage_id, NarrativeProvider())
    build_report_graph(service).invoke({"stage_id": stage_id})
    report = client.get(f"/api/v1/audits/{audit_id}/report").json()
    assert report["ai_report"]["status"] == "ready"
    assert project_name in report["ai_report"]["narrative"]["overview"]
    text = client.get(f"/api/v1/audits/{audit_id}/report.md").text
    assert "AI 修复建议" in text and "替换动态执行" in text
    reused = client.post(
        f"/api/v1/audits/{audit_id}/report-analysis", json={"force": False}
    )
    assert reused.json()["id"] == stage_id
    with Session(engine) as session:
        assert session.get(Candidate, candidate_id).status == "pending"
    decision = client.post(
        f"/api/v1/candidates/{candidate_id}/decisions",
        json={
            "status": "confirmed",
            "reason": "核对实际源码后确认输入可到达动态执行操作",
            "evidence_ids": [evidence["id"]],
        },
    )
    assert decision.status_code == 201
    assert (
        client.get(f"/api/v1/audits/{audit_id}/report").json()["ai_report"]["status"]
        == "stale"
    )
    assert client.get(f"/api/v1/audits/{audit_id}/report.md").status_code == 409
    with Session(engine) as session:
        assert session.get(StageRun, UUID(stage_id)).status == "completed"


def test_failed_report_retry_freezes_current_inputs(pipeline_context, monkeypatch):
    from app.services.report_generation import source_fingerprint
    from app.services.reports import build_report

    context = pipeline_context
    monkeypatch.setattr(stages.execute_stage, "delay", lambda *args: None)
    with Session(engine) as session:
        old = StageRun(
            audit_id=context["run_id"],
            kind="report",
            status="failed",
            error="report_stale",
            inputs={"source_fingerprint": "old"},
        )
        session.add(old)
        session.commit()
        old_id = old.id
        expected = source_fingerprint(
            build_report(session, session.get(AuditRun, context["run_id"]))
        )
    result = context["client"].post(f"/api/v1/stages/{old_id}/retry")
    assert result.status_code == 201
    assert result.json()["inputs"]["source_fingerprint"] == expected
    assert result.json()["id"] != str(old_id)
    with Session(engine) as session:
        assert session.get(StageRun, old_id).status == "failed"
