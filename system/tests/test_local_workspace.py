"""Local entry has no login; storage ownership still preserves task boundaries."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from app.core.config import settings
from app.core.db import engine
from app.main import app
from app.models import User
from app.persistence import workspace
from fastapi.testclient import TestClient
from sqlmodel import Session, delete


def test_existing_history_owner_is_reused_without_credentials(monkeypatch):
    identifier = uuid4()
    email = f"{identifier}@example.com"
    monkeypatch.setattr(settings, "FIRST_SUPERUSER", email)
    with Session(engine) as session:
        session.add(User(id=identifier, email=email, hashed_password="legacy"))
        session.commit()
        try:
            assert workspace.resolve_workspace(session).id == identifier
            assert session.get(User, identifier).hashed_password == "legacy"
        finally:
            session.exec(delete(User).where(User.id == identifier))
            session.commit()


def test_new_workspace_bootstrap_is_stable_under_concurrent_requests(monkeypatch):
    identifier = uuid4()
    monkeypatch.setattr(settings, "FIRST_SUPERUSER", f"{uuid4()}@example.com")
    monkeypatch.setattr(workspace, "WORKSPACE_ID", identifier)
    monkeypatch.setattr(workspace, "WORKSPACE_EMAIL", f"{identifier}@example.com")

    def resolve():
        with Session(engine) as session:
            return workspace.resolve_workspace(session).id

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            assert list(pool.map(lambda _: resolve(), range(3))) == [identifier] * 3
        with Session(engine) as session:
            anchor = session.get(User, identifier)
            assert not anchor.is_active
            assert not anchor.is_superuser
            assert anchor.hashed_password == ""
    finally:
        with Session(engine) as session:
            session.exec(delete(User).where(User.id == identifier))
            session.commit()


def test_local_api_accepts_no_token_and_ignores_stale_tokens(pipeline_context):
    client = pipeline_context["client"]
    identifier = str(pipeline_context["run_id"])
    for headers in ({}, {"Authorization": "Bearer stale-invalid-token"}):
        response = client.get("/api/v1/audits/", headers=headers)
        assert response.status_code == 200
        assert identifier in {row["id"] for row in response.json()}
        assert (
            client.get(f"/api/v1/audits/{identifier}", headers=headers).status_code
            == 200
        )
        assert (
            client.get(
                f"/api/v1/audits/{identifier}/stages", headers=headers
            ).status_code
            == 200
        )
        assert (
            client.get(
                f"/api/v1/audits/{identifier}/repairs", headers=headers
            ).status_code
            == 200
        )
        assert client.get("/api/v1/rules/", headers=headers).status_code == 200
        assert client.get("/api/v1/knowledge/", headers=headers).status_code == 200


def test_account_endpoints_and_oauth_scheme_are_removed():
    with TestClient(app) as client:
        for method, path in (
            ("POST", "/login/access-token"),
            ("POST", "/users/signup"),
            ("GET", "/users/me"),
            ("GET", "/users/"),
            ("GET", "/items/"),
            ("POST", "/private/users/"),
            ("POST", "/utils/test-email/"),
        ):
            assert client.request(method, "/api/v1" + path).status_code == 404
        schema = client.get("/api/v1/openapi.json").json()
        assert not schema["components"].get("securitySchemes")
        assert all(
            "security" not in operation
            for path in schema["paths"].values()
            for operation in path.values()
        )
