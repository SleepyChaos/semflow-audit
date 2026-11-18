import json
from zipfile import ZipFile

"""New Web discovery tasks call the CLI's kernel; use only a disposable SQLite DB."""

from uuid import uuid4

import pytest
from app.adapters.snapshot import snapshot_digest
from app.api.deps import get_db, get_workspace
from app.core.audit_config import audit_settings
from app.main import app
from app.models import User
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import (
    Candidate,
    Decision,
    Evidence,
    RepairRecord,
    StageFollowup,
    StageRun,
)
from app.persistence.workspace import Workspace
from app.research_bridge.models import ResearchAuditBinding, ResearchBinding
from app.services.stage_lifecycle import create_stage_run
from app.services.uploads import create_run
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


class ScoutModel:
    model = "explicit-test-substitute"

    def __init__(self):
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

    def generate(self, purpose, payload, schema):
        self.usage["calls"] += 1
        assert purpose == "scout"
        return schema.model_validate(
            {
                "action": "final",
                "scope_summary": "Read the actual source, trust boundary remains unknown",
                "findings": [
                    {
                        "title": "Dynamic execution",
                        "weakness": "CWE-95",
                        "primary_location": {"file": "app.py", "line": 1},
                        "security_condition": "Untrusted input may reach evaluation",
                        "observation": "The actual source calls eval on input",
                        "missing_premises": ["The caller trust boundary is unknown"],
                        "evidence_ids": [payload["evidence"][0]["id"]],
                    }
                ],
            }
        )


@pytest.fixture
def bridge_case(tmp_path, monkeypatch):
    db = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(
        db,
        tables=[
            m.__table__
            for m in (
                User,
                AuditRun,
                StageRun,
                Evidence,
                Candidate,
                Decision,
                RepairRecord,
                StageFollowup,
                ResearchBinding,
                ResearchAuditBinding,
            )
        ],
    )
    for module in (
        "app.persistence.stage_repository",
        "app.research_bridge.runtime",
        "app.persistence.audit_repository",
        "app.services.evidence",
        "app.research_bridge.scan_runtime",
        "app.research_bridge.repair_runtime",
        "app.research_bridge.rule_runtime",
        "app.research_bridge.repair_integrity",
        "app.services.verification_suites",
        "app.services.repair_comparison",
        "app.services.rule_project_validation",
        "app.application.repair_followups",
    ):
        monkeypatch.setattr(module + ".engine", db)
    monkeypatch.setattr(audit_settings, "ARTIFACT_ROOT", tmp_path)
    monkeypatch.setattr(audit_settings, "AI_MODEL", "explicit-test-substitute")
    monkeypatch.setattr(audit_settings, "AI_BASE_URL", "http://scripted.invalid/v1")
    owner, audit_id = uuid4(), uuid4()
    source = tmp_path / "runs" / str(audit_id) / "source"
    source.mkdir(parents=True)
    (source / "app.py").write_text("value = eval(input())\n")
    with Session(db) as session:
        session.add(
            User(id=owner, email=f"{owner}@example.test", hashed_password="test-only")
        )
        audit = AuditRun(
            id=audit_id,
            owner_id=owner,
            source_run_id=audit_id,
            project_name="synthetic bridge test",
            language="python",
            snapshot_hash=snapshot_digest(source),
            query_pack="codeql/python-queries@test",
            suite="test.qls",
            status="completed",
        )
        session.add(audit)
        session.commit()

    def session_override():
        with Session(db) as session:
            yield session

    app.dependency_overrides[get_db] = session_override
    app.dependency_overrides[get_workspace] = lambda: Workspace(owner)
    yield db, owner, audit_id, source
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_workspace, None)
    db.dispose()


def create_scout(case):
    db, owner, audit_id, _ = case
    with Session(db) as session:
        return create_stage_run(
            session,
            audit_id,
            owner,
            "scout",
            {"max_units": 1, "steps_per_unit": 1},
            prompt_version="1",
        )


@pytest.fixture
def scanner(bridge_case, monkeypatch, tmp_path):
    calls = []
    pack = tmp_path / "packs/codeql/python-queries/test"
    pack.mkdir(parents=True)
    (pack / "test.qls").write_text("- query: example.ql\n")
    (pack / "qlpack.yml").write_text("name: codeql/python-queries\nversion: test\n")
    monkeypatch.setattr(audit_settings, "CODEQL_PACK_PATH", tmp_path / "packs")
    monkeypatch.setattr(
        audit_settings, "PYTHON_QUERY_PACK", "codeql/python-queries@test"
    )
    from semflow_research.adapters.codeql.scanner import CodeQLScanner

    monkeypatch.setattr(CodeQLScanner, "version", lambda self: "scripted-codeql")

    def create(self, source, database, log, plan):
        calls.append("database")
        database.mkdir(parents=True)
        (database / "codeql-database.yml").write_text("scripted: true")
        log.write_text("Explicit scanner substitute; no real CodeQL evaluation")

    def analyze(self, database, output, log, plan):
        calls.append("analyze")
        output.write_text(
            json.dumps(
                {
                    "version": "2.1.0",
                    "runs": [
                        {
                            "tool": {"driver": {"rules": []}},
                            "invocations": [{"executionSuccessful": True}],
                            "results": [
                                {
                                    "ruleId": "py/code-injection",
                                    "message": {"text": "Input reaches eval"},
                                    "locations": [
                                        {
                                            "physicalLocation": {
                                                "artifactLocation": {"uri": "app.py"},
                                                "region": {"startLine": 1},
                                            }
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            )
        )

    monkeypatch.setattr(CodeQLScanner, "create_database", create)
    monkeypatch.setattr(CodeQLScanner, "analyze", analyze)
    return calls


def upload(case, *, dual=False, extra_sources=None):
    db, owner, _, source = case
    archive = source.parent / "new-upload.zip"
    with ZipFile(archive, "w") as stream:
        stream.write(source / "app.py", "app.py")
        for name, content in (extra_sources or {}).items():
            stream.writestr(name, content)
    with Session(db) as session:
        return create_run(
            session,
            owner,
            archive,
            "synthetic scan bridge",
            "python",
            dual_engine=dual,
            suite="test.qls",
        )


class CurrentScoutModel(ScoutModel):
    def for_execution(self, context):
        return type(self)()

    def generate(self, purpose, payload, schema):
        from semflow_contracts.modelio.scouting import ScoutResponse

        body = super().generate(purpose, payload, ScoutResponse).model_dump(mode="json")
        body["findings"][0].update(
            security_property="input_injection", operation_quote="eval(input())"
        )
        body["task_checks"] = [
            {
                "task_id": task["id"],
                "status": "unknown",
                "conclusion": "unknown",
                "reason": "The actual source was read but caller trust is still unknown",
                "evidence_ids": [],
            }
            for task in payload["inspection_tasks"]
        ]
        body["route_checks"] = []
        return schema.model_validate(body)
