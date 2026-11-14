"""Platform authorization fixture with actual persisted source evidence."""

import hashlib
from uuid import UUID

from app.main import app
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, Decision, Evidence, StageRun
from app.runtime.scans import run_scan
from app.services.stage_lifecycle import create_stage_run
from fastapi.testclient import TestClient
from sqlmodel import Session

from tests.research_bridge_cases import upload


def create_confirmed_repair(bridge_case, *, engine="native"):
    db, owner, _, _ = bridge_case
    audit = upload(bridge_case)
    assert run_scan(str(audit.id)).status == "completed"
    with Session(db) as session:
        source = session.get(AuditRun, audit.id)
        scout = StageRun(
            audit_id=audit.id,
            kind="scout",
            status="completed",
            phase="hypotheses_ready",
        )
        session.add(scout)
        session.flush()
        evidence = Evidence(
            stage_id=scout.id,
            audit_id=audit.id,
            kind="code",
            snapshot_hash=source.snapshot_hash,
            reference={"file": "app.py", "start_line": 1, "end_line": 1},
            content="value = eval(input())",
            digest=hashlib.sha256(b"value = eval(input())").hexdigest(),
        )
        session.add(evidence)
        session.flush()
        candidate = Candidate(
            audit_id=audit.id,
            stage_id=scout.id,
            origin="static",
            title="eval",
            description="Dynamic evaluation from input",
            status="confirmed",
            evidence_ids=[str(evidence.id)],
            identity_key="static:test",
            weakness="CWE-95",
            location={"file": "app.py", "line": 1, "end_line": 1},
        )
        session.add(candidate)
        session.flush()
        actor = owner
        session.add(candidate)
        decision = Decision(
            candidate_id=candidate.id,
            actor_id=actor,
            status="confirmed",
            reason="Operator explicitly reviewed the exact source evidence",
            evidence_ids=candidate.evidence_ids,
        )
        session.add(decision)
        session.commit()
        stage = create_stage_run(
            session,
            audit.id,
            owner,
            "repair",
            {
                "engine": engine,
                "candidate_ids": [str(candidate.id)],
                "allowed_paths": ["app.py"],
                "validation_profile": "syntax",
                "rescan": False,
            },
            prompt_version="4",
        )
        return stage.id


def request_from_panel(case, monkeypatch, *, link_static=True):
    original = create_confirmed_repair(case)
    with Session(case[0]) as session:
        previous = session.get(StageRun, original)
        previous.status = "completed"
        session.add(previous)
        audit = session.get(AuditRun, previous.audit_id)
        candidate = session.get(Candidate, UUID(previous.inputs["candidate_ids"][0]))
        if link_static:
            candidate.static_finding_id = audit.findings[0]["id"]
            session.add(candidate)
        session.commit()
        audit_id, candidate_id = audit.id, candidate.id
    published = []
    monkeypatch.setattr(
        "app.jobs.stages.execute_stage.delay", lambda *args: published.append(args)
    )
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/audits/{audit_id}/repair",
            json={
                "candidate_ids": [str(candidate_id)],
                "allowed_paths": [],
                "validation_profile": "syntax",
                "rescan": True,
            },
        )
        assert response.status_code == 201, response.text
        stage_id = UUID(response.json()["id"])
    assert published == [(str(stage_id), False)]
    return stage_id, audit_id
