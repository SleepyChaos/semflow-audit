import io
from datetime import timedelta
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.db import engine
from app.core.security import create_access_token
from app.core.audit_config import audit_settings
from app.main import app
from app.models import User
from app.persistence.audit_models import AuditRun
from app.api.routes.audits import execute_scan


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(audit_settings, "ARTIFACT_ROOT", tmp_path)
    identifier = uuid4()
    with Session(engine) as session:
        session.add(
            User(
                id=identifier,
                email=f"{identifier}@example.com",
                hashed_password="test-only",
            )
        )
        session.commit()
    token = create_access_token(identifier, timedelta(minutes=5))
    with TestClient(app) as test_client:
        test_client.headers["Authorization"] = "Bearer " + token
        yield test_client, identifier
    with Session(engine) as session:
        session.exec(delete(AuditRun).where(AuditRun.owner_id == identifier))
        session.exec(delete(User).where(User.id == identifier))
        session.commit()


def sample():
    stream = io.BytesIO()
    with ZipFile(stream, "w") as bundle:
        bundle.writestr("app.py", "print('safe')")
    return stream.getvalue()


def upload(client):
    return client.post(
        "/api/v1/audits/",
        files={"file": ("project.zip", sample())},
        data={"language": "python"},
    )


def test_upload_dispatch_and_owner_isolation(client, monkeypatch):
    api, owner = client
    dispatched = []
    monkeypatch.setattr(
        execute_scan, "delay", lambda identifier: dispatched.append(identifier)
    )
    result = upload(api)
    assert result.status_code == 201
    assert result.json()["suite"] == "codeql-suites/python-code-scanning.qls"
    assert result.json()["coverage"]["pipeline_version"] == "2"
    identifier = result.json()["id"]
    assert dispatched == [identifier]
    assert (
        api.get(
            f"/api/v1/audits/{identifier}/source",
            params={"file": "../outside", "line": 1},
        ).status_code
        == 404
    )
    assert api.get(
        f"/api/v1/audits/{identifier}/source", params={"file": "app.py", "line": 1}
    ).json()["lines"] == ["print('safe')"]
    other = uuid4()
    with Session(engine) as session:
        session.add(
            User(id=other, email=f"{other}@example.com", hashed_password="test-only")
        )
        session.commit()
    api.headers["Authorization"] = "Bearer " + create_access_token(
        other, timedelta(minutes=5)
    )
    assert api.get(f"/api/v1/audits/{identifier}").status_code == 404
    assert api.get(f"/api/v1/audits/{identifier}/logs").status_code == 404
    assert api.get("/api/v1/audits/").json() == []
    with Session(engine) as session:
        session.exec(delete(User).where(User.id == other))
        session.commit()


def test_dispatch_failure_is_explicit_and_retry_has_new_identity(client, monkeypatch):
    api, _ = client

    def unavailable(_):
        raise ConnectionError("broker unavailable")

    monkeypatch.setattr(execute_scan, "delay", unavailable)
    original = upload(api).json()
    assert original["status"] == "failed"
    assert "队列" in original["error"]
    monkeypatch.setattr(execute_scan, "delay", lambda _: None)
    retried = api.post(f"/api/v1/audits/{original['id']}/retry").json()
    assert retried["id"] != original["id"]
    assert retried["snapshot_hash"] == original["snapshot_hash"]
    assert retried["suite"] == original["suite"]
    assert retried["coverage"]["pipeline_version"] == "2"
    assert api.get(f"/api/v1/audits/{original['id']}").json()["status"] == "failed"


def test_malformed_archive_does_not_create_a_run(client):
    api, _ = client
    response = api.post(
        "/api/v1/audits/",
        files={"file": ("bad.zip", b"broken")},
        data={"language": "python"},
    )
    assert response.status_code == 422
    assert api.get("/api/v1/audits/").json() == []


def test_cancel_prevents_claim_and_completion_and_retry_is_independent(
    client, monkeypatch
):
    from app.persistence.audit_repository import AuditRepository
    from app.domain.audit import AuditCancelled

    api, _ = client
    monkeypatch.setattr(execute_scan, "delay", lambda _: None)
    original = upload(api).json()
    identifier = original["id"]
    cancelled = api.post(f"/api/v1/audits/{identifier}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    repository = AuditRepository()
    assert not repository.claim(identifier)
    with pytest.raises(AuditCancelled):
        repository.update(identifier, status="completed", findings=[])
    retried = api.post(f"/api/v1/audits/{identifier}/retry")
    assert retried.status_code == 201
    assert retried.json()["id"] != identifier
    assert retried.json()["snapshot_hash"] == original["snapshot_hash"]


def test_recover_rejects_recent_execution_and_stops_stale_execution(
    client, monkeypatch
):
    from datetime import UTC, datetime
    from uuid import UUID
    from app.persistence.audit_repository import AuditRepository

    api, _ = client
    monkeypatch.setattr(execute_scan, "delay", lambda _: None)
    identifier = upload(api).json()["id"]
    assert AuditRepository().claim(identifier)
    assert api.post(f"/api/v1/audits/{identifier}/recover").status_code == 409
    with Session(engine) as session:
        run = session.get(AuditRun, UUID(identifier))
        run.updated_at = datetime.now(UTC) - timedelta(minutes=46)
        session.add(run)
        session.commit()
    response = api.post(f"/api/v1/audits/{identifier}/recover")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
