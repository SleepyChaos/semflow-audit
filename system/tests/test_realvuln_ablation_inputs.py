"""Independent review arms retain real evidence and never inherit verdicts."""

from uuid import UUID, uuid4

import pytest
from app.adapters.snapshot import snapshot_digest
from app.core.audit_config import audit_settings
from app.models import User
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, Evidence, StageRun
from scripts.benchmarks import realvuln_ablation_inputs as inputs
from scripts.benchmarks.realvuln_prepare import save
from sqlmodel import Session, create_engine, select


def test_scout_only_and_static_only_inputs_are_isolated(tmp_path, monkeypatch):
    database = create_engine("sqlite://")
    for model in (User, AuditRun, StageRun, Evidence, Candidate):
        model.__table__.create(database)
    monkeypatch.setattr(inputs, "engine", database)
    monkeypatch.setattr(audit_settings, "ARTIFACT_ROOT", tmp_path / "artifacts")
    origin, output, project = tmp_path / "origin", tmp_path / "output", "sample"
    source = origin / "sources" / project
    source.mkdir(parents=True)
    content = "danger = eval(input())\n"
    (source / "app.py").write_text(content)
    snapshot = snapshot_digest(source)
    audit_id, owner = uuid4(), uuid4()
    with Session(database) as db:
        db.add(
            User(
                id=owner,
                email="ablation-test@research.invalid",
                hashed_password="disabled",
            )
        )
        db.commit()
        audit = AuditRun(
            id=audit_id,
            owner_id=owner,
            source_run_id=audit_id,
            project_name=project,
            language="python",
            snapshot_hash=snapshot,
            query_pack="test@1",
            suite="test",
        )
        db.add(audit)
        db.commit()
        stage = StageRun(audit_id=audit_id, kind="scout")
        db.add(stage)
        db.commit()
        db.refresh(stage)
        evidence = Evidence(
            audit_id=audit_id,
            stage_id=stage.id,
            kind="code",
            snapshot_hash=snapshot,
            reference={"file": "app.py", "start_line": 1, "end_line": 1},
            content=content,
            digest=__import__("hashlib").sha256(content.encode()).hexdigest(),
        )
        db.add(evidence)
        db.commit()
        db.refresh(evidence)
        candidate = Candidate(
            audit_id=audit_id,
            stage_id=stage.id,
            origin="ai",
            title="source flow",
            description="Input reaches the actual eval binding",
            identity_key="scout:test",
            weakness="CWE-95",
            location={"file": "app.py", "line": 1},
            evidence_ids=[str(evidence.id)],
            status="confirmed",
            model_assessment="supported",
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        raw = candidate.model_dump(mode="json")
        db.refresh(stage)
        scout_stage = stage.model_dump(mode="json")
    scout = {"stage_id": scout_stage["id"], "stage": scout_stage, "candidates": [raw]}
    save(origin / "system" / project / "scout.json", scout)
    alert = {"id": "static-id", "locations": [{"file": "app.py", "line": 1}]}
    save(
        origin / "static" / project / "result.json",
        {
            "status": "succeeded",
            "snapshot": snapshot,
            "pack": "test@1",
            "suite": "test",
            "rounds": [{"findings": [alert]}],
        },
    )
    save(origin / "config.json", {"codeql_cli": "test"})
    catalog = {scout_stage["id"]: {"stage": scout_stage}}
    static_only = inputs.register(project, "D", origin, output, catalog)
    scout_only = inputs.register(project, "E", origin, output, catalog)
    assert static_only["audit_id"] != scout_only["audit_id"]
    with Session(database) as db:
        assert db.get(AuditRun, UUID(static_only["audit_id"])).findings == [alert]
        assert db.get(AuditRun, UUID(scout_only["audit_id"])).findings == []
        imported = db.exec(
            select(Candidate).where(Candidate.audit_id == UUID(scout_only["audit_id"]))
        ).one()
        assert imported.status == imported.model_assessment == "pending"
        assert str(imported.id) != raw["id"]
        cloned_evidence = db.get(Evidence, UUID(imported.evidence_ids[0]))
        assert cloned_evidence.content == content
        assert cloned_evidence.audit_id == imported.audit_id
        assert str(cloned_evidence.id) != raw["evidence_ids"][0]
        assert not db.exec(
            select(StageRun).where(
                StageRun.audit_id == UUID(static_only["audit_id"]),
                StageRun.kind == "scout",
            )
        ).all()
        original_evidence = db.get(Evidence, UUID(raw["evidence_ids"][0]))
        original_evidence.content += "tampered\n"
        db.add(original_evidence)
        db.commit()
    with pytest.raises(RuntimeError, match="evidence identity/content mismatch"):
        inputs.register(project, "F", origin, output, catalog)
    assert not (output / "arms/F/system/sample/input.json").exists()
