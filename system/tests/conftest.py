from uuid import uuid4
from zipfile import ZipFile

import pytest
from app.api.deps import get_workspace
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.main import app
from app.models import User
from app.persistence.audit_models import AuditRun
from app.persistence.knowledge_models import KnowledgeChunk, RuleVersion
from app.persistence.stage_models import (
    Candidate,
    Decision,
    Evidence,
    RepairRecord,
    StageRun,
)
from app.persistence.workspace import Workspace
from app.services.uploads import create_run
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select


@pytest.fixture
def pipeline_context(monkeypatch, tmp_path, request):
    monkeypatch.setattr(audit_settings, "ARTIFACT_ROOT", tmp_path)
    # Ordinary tests must not inherit a real embedding gateway from local .env.
    # Vector integration tests opt in explicitly with their deterministic embedder.
    monkeypatch.setattr(audit_settings, "EMBEDDING_MODEL", "")
    user_id = uuid4()
    with Session(engine) as session:
        session.add(
            User(
                id=user_id, email=f"{user_id}@example.com", hashed_password="test-only"
            )
        )
        session.commit()
        archive = tmp_path / "test.zip"
        with ZipFile(archive, "w") as bundle:
            if request.node.get_closest_marker("integration") and not hasattr(
                request, "param"
            ):
                from pathlib import Path

                fixtures = Path(__file__).parent / "fixtures/vulnerable"
                for path in fixtures.iterdir():
                    bundle.write(path, path.name)
            else:
                files = getattr(request, "param", {"app.py": "value = eval(input())\n"})
                for name, content in files.items():
                    bundle.writestr(name, content)
        run = create_run(session, user_id, archive, "pipeline-test", "python")
        run.status, run.phase = "completed", "completed"
        run.findings = [
            {
                "id": "static-eval",
                "rule": "py/code-injection",
                "message": "Untrusted input reaches eval",
                "locations": [
                    {"file": "app.py", "line": 1, "column": 9, "end_line": 1}
                ],
                "code_flows": [],
            }
        ]
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id
    with TestClient(app) as client:
        monkeypatch.setitem(
            app.dependency_overrides, get_workspace, lambda: Workspace(user_id)
        )
        yield {"client": client, "owner": user_id, "run_id": run_id, "root": tmp_path}
    with Session(engine) as session:
        run_ids = session.exec(
            select(AuditRun.id).where(AuditRun.owner_id == user_id)
        ).all()
        stage_ids = session.exec(
            select(StageRun.id).where(StageRun.audit_id.in_(run_ids))
        ).all()
        candidate_ids = session.exec(
            select(Candidate.id).where(Candidate.audit_id.in_(run_ids))
        ).all()
        if candidate_ids:
            session.exec(
                delete(Decision).where(Decision.candidate_id.in_(candidate_ids))
            )
        for model in [RuleVersion, RepairRecord, Evidence, Candidate, StageRun]:
            session.exec(delete(model).where(model.audit_id.in_(run_ids)))
        session.exec(delete(KnowledgeChunk).where(KnowledgeChunk.owner_id == user_id))
        session.exec(delete(AuditRun).where(AuditRun.id.in_(run_ids)))
        session.exec(delete(User).where(User.id == user_id))
        from sqlalchemy import text

        # Only synthetic test thread IDs, never global checkpoint schema or user history.
        for table in ["checkpoint_writes", "checkpoint_blobs", "checkpoints"]:
            exists = session.execute(
                text("SELECT to_regclass(:table)").bindparams(table=table)
            ).scalar()
            if exists:
                for identifier in [*stage_ids, *run_ids]:
                    session.execute(
                        text(
                            f"DELETE FROM {table} WHERE thread_id = :identifier"
                        ).bindparams(identifier=str(identifier))
                    )
        session.commit()
