"""Fixed synthetic rule inputs and external tool/model substitutes for Web tests."""

import hashlib
from uuid import uuid4
from zipfile import ZipFile

import yaml
from app.core.audit_config import audit_settings
from app.main import app
from app.persistence.audit_models import AuditRun
from app.persistence.knowledge_models import KnowledgeChunk, RuleVersion
from app.persistence.stage_models import StageRun
from fastapi.testclient import TestClient
from sqlmodel import Session

from research.tests.rule_cases import QUERY, install_substitutes
from tests.research_repair_cases import create_confirmed_repair


def setup_rule(case, monkeypatch, *, with_holdout=False, missing_corpus=False):
    phases = []
    install_substitutes(monkeypatch, phases)
    monkeypatch.setattr(audit_settings, "EMBEDDING_MODEL", "")
    monkeypatch.setattr(audit_settings, "SEMANTIC_CONTEXT_CHARS", 40000)
    from app.adapters.codeql.scanner import CodeQLScanner as LegacyScanner
    from semflow_research.adapters.codeql.scanner import CodeQLScanner

    monkeypatch.setattr(LegacyScanner, "version", lambda self: "scripted-codeql")
    create_database = CodeQLScanner.create_database

    def create(self, source, database, log, plan):
        create_database(self, source, database, log, plan)
        (database / "codeql-database.yml").write_text(
            yaml.safe_dump(
                {
                    "sourceLocationPrefix": str(source),
                    "primaryLanguage": "python",
                    "creationMetadata": {"cliVersion": "scripted-codeql"},
                    "finalised": True,
                }
            )
        )
        with ZipFile(database / "src.zip", "w") as archive:
            for path in source.rglob("*.py"):
                archive.writestr(path.as_posix().lstrip("/"), path.read_bytes())

    monkeypatch.setattr(CodeQLScanner, "create_database", create)

    from research.tests.rule_replay_cases import install_replay

    install_replay(monkeypatch, phases)
    for model in (KnowledgeChunk, RuleVersion):
        model.__table__.create(case[0], checkfirst=True)
    pack = audit_settings.CODEQL_PACK_PATH / "codeql/python-queries/test"
    (pack / "codeql-pack.lock.yml").write_text(
        "dependencies:\n  codeql/python-all:\n    version: test\n"
    )
    template = pack / "Security/CWE-094/CodeInjection.ql"
    template.parent.mkdir(parents=True)
    template.write_text(QUERY)
    library = audit_settings.CODEQL_PACK_PATH / "codeql/python-all/test"
    library.mkdir(parents=True)
    (library / "qlpack.yml").write_text(
        "name: codeql/python-all\nversion: test\nlibrary: true\n"
    )
    repair_id = create_confirmed_repair(case)
    with Session(case[0]) as session:
        repair = session.get(StageRun, repair_id)
        repair.status = "cancelled"
        session.add(repair)
        audit = session.get(AuditRun, repair.audit_id)
        candidate = repair.inputs["candidate_ids"][0]
        if not missing_corpus:
            entries = [
                ("reference", "Python CodeInjectionQuery API"),
                ("reference", "Python CodeInjectionCustomizations API"),
                ("reference", "Python ApiGraphs API"),
                ("rule_example", "CodeQL CWE-094 eval example"),
            ]
            for collection, title in entries:
                content = (
                    "CodeQL eval moduleImport getMember getACall class Source Python API "
                    + QUERY
                )
                session.add(
                    KnowledgeChunk(
                        owner_id=audit.owner_id,
                        document_id=uuid4(),
                        version="v1",
                        title=title,
                        source="rule-fixture:" + title,
                        language="python",
                        position=0,
                        content=content,
                        digest=hashlib.sha256(content.encode()).hexdigest(),
                        corpus=collection,
                        provenance={
                            "api_version": "test",
                            "cwe_ids": ["CWE-094"],
                            "validation": {"status": "passed", "kind": "compile_only"},
                        },
                    )
                )
        session.commit()
        audit_id = audit.id
    published = []
    monkeypatch.setattr(
        "app.jobs.stages.execute_stage.delay", lambda *args: published.append(args)
    )
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/audits/{audit_id}/rule",
            json={
                "candidate_id": candidate,
                "purpose": "vulnerability_detector",
                "strategy": "auto",
                "source_paths": [],
                "requirement": "Detect direct eval calls linked to the confirmed source evidence",
                "holdout_id": "python-eval-vulnerability_detector-v1"
                if with_holdout
                else None,
            },
        )
        assert response.status_code == 201, response.text
    return response.json()["id"], phases, published
