"""CLI integration uses scripted model responses, real graphs, CodeQL and Docker."""

import os
from uuid import UUID
import pytest
from sqlmodel import Session, select
from app.adapters.artifacts import ArtifactStore
from app.core.db import engine
from app.jobs.scan import execute_scan
from app.jobs.stages import execute_stage
from app.persistence.audit_models import AuditRun
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import StageRun
from tests.model_fixtures import ScriptedModel

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("AUDIT_RUN_REAL_TOOLS") != "1",
        reason="Enable actual local tools explicitly",
    ),
]


def test_full_pipeline_with_real_codeql_docker_and_checkpoint_resume(
    pipeline_context, monkeypatch
):
    ctx = pipeline_context
    with Session(engine) as session:
        run = session.get(AuditRun, ctx["run_id"])
        run.status = "queued"
        session.add(run)
        session.commit()
    execute_scan.run(str(ctx["run_id"]))
    api = ctx["client"]
    audit = api.get(f"/api/v1/audits/{ctx['run_id']}").json()
    assert audit["status"] == "completed", audit.get("error")
    assert any(row["rule"] == "py/code-injection" for row in audit["findings"])
    import app.jobs.stages as tasks

    monkeypatch.setattr(tasks, "CompatibleModel", ScriptedModel)
    monkeypatch.setattr(
        execute_stage,
        "delay",
        lambda identifier, resume=False: execute_stage.run(identifier, resume),
    )
    response = api.post(f"/api/v1/audits/{ctx['run_id']}/review", json={"max_steps": 8})
    assert response.status_code == 201, response.text
    review = api.get(f"/api/v1/stages/{response.json()['id']}").json()
    assert review["status"] == "completed", review.get("error")
    candidate = api.get(f"/api/v1/audits/{ctx['run_id']}/candidates").json()[0]
    assert candidate["status"] == "pending"
    confirmed = api.post(
        f"/api/v1/candidates/{candidate['id']}/decisions",
        json={
            "status": "confirmed",
            "reason": "Reviewed the sample input-to-eval path and verified absence of protection.",
            "evidence_ids": candidate["evidence_ids"],
        },
    )
    assert confirmed.status_code == 201, confirmed.text
    original = ArtifactStore().source(str(ctx["run_id"])) / "app.py"
    original_text = original.read_text()
    response = api.post(
        f"/api/v1/audits/{ctx['run_id']}/repair",
        json={"candidate_ids": [candidate["id"]], "rescan": True},
    )
    assert response.status_code == 201, response.text
    repair_stage = api.get(f"/api/v1/stages/{response.json()['id']}").json()
    assert repair_stage["status"] == "completed", repair_stage.get("error")
    repair = api.get(f"/api/v1/audits/{ctx['run_id']}/repairs").json()[0]
    assert repair["status"] == "checks_passed", repair["validation"]
    assert original.read_text() == original_text
    diff = api.get(f"/api/v1/repairs/{repair['id']}/diff")
    assert diff.status_code == 200 and "+    return str(int(expression))" in diff.text
    assert (
        api.post(
            f"/api/v1/repairs/{repair['id']}/accept",
            json={
                "reason": "Reviewed limited numeric conversion and passing syntax and rescan results."
            },
        ).status_code
        == 200
    )
    response = api.post(
        f"/api/v1/audits/{ctx['run_id']}/rule",
        json={
            "requirement": "Python eval 动态执行 CodeQL 自定义规则审计锚点",
            "strategy": "new_query",
            "candidate_id": candidate["id"],
        },
    )
    assert response.status_code == 201, response.text
    rule_stage_id = response.json()["id"]
    stage = api.get(f"/api/v1/stages/{rule_stage_id}").json()
    assert stage["status"] == "awaiting_confirmation", stage.get("error")
    rule = next(
        row
        for row in api.get("/api/v1/rules/").json()
        if row["stage_id"] == rule_stage_id
    )
    assert api.post(f"/api/v1/rules/{rule['id']}/publish").status_code == 409
    approval = api.post(
        f"/api/v1/rules/{rule['id']}/approve-fixtures",
        json={
            "reason": "Checked positive eval case and negative numeric conversion, including expected source lines."
        },
    )
    assert approval.status_code == 200, approval.text
    stage = api.get(f"/api/v1/stages/{rule_stage_id}").json()
    assert stage["status"] == "completed", stage.get("error")
    rule = api.get(f"/api/v1/rules/{rule['id']}").json()
    assert rule["status"] == "validated", rule["validation"]
    assert rule["validation"]["tests"]["positive"]["actual"] == [["positive.py", 1]]
    assert rule["validation"]["tests"]["negative"]["actual"] == []
    assert api.post(f"/api/v1/rules/{rule['id']}/publish").status_code == 200
    # A new upload explicitly freezes a published version and keeps both SARIF origins.
    monkeypatch.setattr(
        execute_scan, "delay", lambda identifier: execute_scan.run(identifier)
    )
    with (ArtifactStore().directory(str(ctx["run_id"])) / "upload.zip").open(
        "rb"
    ) as archive:
        uploaded = api.post(
            "/api/v1/audits/",
            files={"file": ("supplement.zip", archive)},
            data={"language": "python", "rule_ids": rule["id"]},
        )
    assert uploaded.status_code == 201, uploaded.text
    supplemented = api.get(f"/api/v1/audits/{uploaded.json()['id']}").json()
    assert supplemented["status"] == "completed", supplemented.get("error")
    assert any(row["rule_version"] == rule["id"] for row in supplemented["findings"])
    assert any(row["origin"] == "baseline" for row in supplemented["findings"])
    assert (ArtifactStore().directory(supplemented["id"]) / "baseline.sarif").is_file()
    assert api.get(f"/api/v1/audits/{supplemented['id']}/sarif").status_code == 200
    from app.services.rules_execution import execute_evidence_query
    from app.services.evidence import EvidenceService

    evidence = execute_evidence_query(
        EvidenceService(str(ctx["run_id"]), review["id"], []), rule["id"]
    )
    assert evidence["kind"] == "query" and "custom/dynamic-eval" in evidence["content"]
    report = api.get(f"/api/v1/audits/{ctx['run_id']}/report").json()
    assert report["repairs"][0]["status"] == "accepted"
    assert report["rules"][0]["status"] == "published"
    assert report["summary"]["candidate_states"]["confirmed"] == 1
    print(
        "Real tools: static scan, bounded review, human confirmation, isolated repair, rescan, RAG, checkpoint approval, positive/negative tests, publish and evidence query passed."
    )
