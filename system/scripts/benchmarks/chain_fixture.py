"""Prepare immutable end-to-end inputs and clean only recorded test actors."""

import argparse
import json
from pathlib import Path
from uuid import UUID, uuid4
from zipfile import ZipFile

from app.adapters.ai.policy import policy_snapshot
from app.adapters.codeql.custom import fixed_dependencies
from app.core.db import engine
from app.core.security import get_password_hash
from app.models import User, UserBase
from app.persistence.audit_models import AuditRun
from app.persistence.knowledge_models import KnowledgeChunk, RuleVersion
from app.persistence.stage_models import (
    Candidate,
    Decision,
    Evidence,
    RepairRecord,
    StageRun,
)
from app.services.context_materials import digest
from sqlalchemy import text
from sqlmodel import Session, delete, select

from scripts.benchmarks.chain_cases import hidden_tests, projects
from scripts.benchmarks.supplemental_prepare import ROOT, save, sha


def prepare(output):
    if (output / "config.json").exists():
        raise RuntimeError("Never overwrite a campaign freeze")
    actors = []
    with Session(engine) as db:
        for role in ("primary", "other"):
            identifier = uuid4()
            actor = {
                "id": str(identifier),
                "email": f"chain-{identifier}@example.com",
                "password": "Chain-test-" + uuid4().hex,
                "role": role,
            }
            profile = UserBase.model_validate(
                {"email": actor["email"], "is_active": True}
            )
            user = User(
                id=identifier,
                hashed_password=get_password_hash(actor["password"]),
                **profile.model_dump(),
            )
            db.add(user)
            actors.append(actor)
        db.commit()
    save(output / "credentials.private.json", actors)
    (output / "credentials.private.json").chmod(0o600)
    records = []
    for language, files in projects().items():
        source = output / "inputs" / language
        source.mkdir(parents=True)
        archive = output / "inputs" / (language + ".zip")
        with ZipFile(archive, "w") as bundle:
            for name, content in files.items():
                (source / name).write_text(content)
                bundle.writestr(name, content)
        records.append(
            {
                "language": language,
                "archive": str(archive),
                "sha256": sha(archive),
                "source_hashes": {name: sha(source / name) for name in files},
                "business_contract_visible": True,
            }
        )
    save(output / "inputs.json", {"records": records})
    save(output / "evaluator-only/hidden-tests.json", hidden_tests())
    with Session(engine) as db:
        chunks = db.exec(
            select(KnowledgeChunk).where(KnowledgeChunk.owner_id.is_(None))
        ).all()
        corpus = [
            {
                "id": str(row.id),
                "document_id": str(row.document_id),
                "version": row.version,
                "corpus": row.corpus,
                "content_sha256": digest(row.content),
                "embedding_sha256": digest([float(v) for v in row.embedding])
                if row.embedding is not None
                else None,
                "embedding_identity": row.embedding_identity,
            }
            for row in chunks
        ]
    save(
        output / "corpus-identity-receipt.json",
        {
            "shared_chunks": len(corpus),
            "hash": digest(sorted(corpus, key=lambda row: row["id"])),
            "records": corpus,
        },
    )
    save(
        output / "config.json",
        {
            "campaign_id": "20261009-chain-completion-v1",
            "queue": "semflow-chain-20261009-v1",
            "url": "http://localhost:5173",
            "api_url": "http://localhost:8000",
            "artifact_root": str(output / "runtime"),
            "production_hashes": {
                p.relative_to(ROOT).as_posix(): sha(p)
                for folder in ("system/backend/app", "system/frontend/src")
                for p in (ROOT / folder).rglob("*")
                if p.is_file() and p.suffix in {".py", ".txt", ".tsx", ".ts", ".css"}
            },
            "runner_hashes": {
                p.relative_to(ROOT).as_posix(): sha(p)
                for p in (ROOT / "system/scripts/benchmarks").glob("chain*")
                if p.is_file()
            },
            "locks": {
                p: sha(ROOT / p) for p in ("system/uv.lock", "system/frontend/package-lock.json")
            },
            "model_policy_before_execution": policy_snapshot(),
            "effective_caps": {"calls": 20, "tokens": 160000, "seconds": 480},
            "limits": {
                "main_projects": 2,
                "rule_reuse_uploads": 2,
                "rule_requests_per_language": 1,
                "repair_requests_per_language": 1,
            },
            "library_versions": {
                language: fixed_dependencies(language)["codeql/" + language + "-all"][
                    "version"
                ]
                for language in ("python", "javascript")
            },
            "versions": {"scout": "7", "review": "9", "repair": "2", "rule": "8"},
            "confirmation_origin": "automated_test_actor_after_fixture_evidence_check_not_independent_human_review",
            "scope": "Real browser/upload/queue/Worker/models/tools/database/approval/publication/reuse/download for two derived projects; failure/safety regression separate; no natural-CVE population claim",
        },
    )


def cleanup(output):
    private = output / "credentials.private.json"
    actors = json.loads(private.read_text())
    totals = {"users": 0, "audits": 0, "stages": 0}
    with Session(engine) as db:
        for actor in actors:
            owner = UUID(actor["id"])
            user = db.get(User, owner)
            if (
                user is None
                or user.email != actor["email"]
                or not user.email.startswith("chain-")
            ):
                raise RuntimeError("Refuse cleanup of an unexpected actor")
            audits = db.exec(select(AuditRun).where(AuditRun.owner_id == owner)).all()
            if any(not row.project_name.startswith("chain-") for row in audits):
                raise RuntimeError("Unexpected owned project; preserve for inspection")
            run_ids = [r.id for r in audits]
            stage_ids = db.exec(
                select(StageRun.id).where(StageRun.audit_id.in_(run_ids))
            ).all()
            candidates = db.exec(
                select(Candidate.id).where(Candidate.audit_id.in_(run_ids))
            ).all()
            if candidates:
                db.exec(delete(Decision).where(Decision.candidate_id.in_(candidates)))
            for model in (RuleVersion, RepairRecord, Evidence, Candidate, StageRun):
                db.exec(delete(model).where(model.audit_id.in_(run_ids)))
            db.exec(delete(RuleVersion).where(RuleVersion.owner_id == owner))
            db.exec(delete(KnowledgeChunk).where(KnowledgeChunk.owner_id == owner))
            db.exec(delete(AuditRun).where(AuditRun.owner_id == owner))
            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                if db.execute(
                    text("SELECT to_regclass(:table)").bindparams(table=table)
                ).scalar():
                    for identifier in [*run_ids, *stage_ids]:
                        db.execute(
                            text(f"DELETE FROM {table} WHERE thread_id=:id").bindparams(
                                id=str(identifier)
                            )
                        )
            db.delete(user)
            totals["users"] += 1
            totals["audits"] += len(run_ids)
            totals["stages"] += len(stage_ids)
        db.commit()
    private.unlink()
    save(
        output / "cleanup-receipt.json",
        {
            **totals,
            "credentials_removed": True,
            "runtime_files_retained_for_archive": True,
            "unrelated_tasks_deleted": False,
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "cleanup"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    {"prepare": prepare, "cleanup": cleanup}[args.action](args.output.resolve())


if __name__ == "__main__":
    main()
