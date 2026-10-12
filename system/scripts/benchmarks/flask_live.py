"""Real provider rule ablation and triage pilot; oracle is evaluator-only."""

import argparse
import hashlib
import json
import logging
import time
from pathlib import Path
from uuid import UUID, uuid4
from zipfile import ZipFile

from app.adapters.ai.policy import policy_snapshot
from app.adapters.ai.provider import CompatibleModel
from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.custom import prepare_query, run_query
from app.adapters.retrieval.knowledge import import_knowledge
from app.contracts.review import ReviewResponseV2
from app.core.db import engine
from app.jobs.stages import execute_stage
from app.models import User
from app.persistence.audit_models import AuditRun
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import Candidate, StageRun
from app.services.review import ReviewService
from app.services.uploads import create_run
from sqlmodel import Session, select

from scripts.benchmarks.flask_cases import score
from scripts.benchmarks.rule_ablation import initialize

ROOT = Path(__file__).resolve().parents[3]
ARMS = {
    "free_ql": {"routing": True, "full_feedback": True, "framework_knowledge": True},
    "typed_route": {
        "routing": True,
        "full_feedback": True,
        "framework_knowledge": True,
        "flask_route_spec": True,
    },
    "typed_route_dev": {
        "routing": True,
        "full_feedback": True,
        "framework_knowledge": True,
        "flask_route_spec": True,
        "execute_dev": True,
    },
}


def stage(audit_id, kind, inputs, policy, version):
    with Session(engine) as db:
        row = StageRun(
            audit_id=UUID(audit_id),
            kind=kind,
            inputs=inputs,
            prompt_version=version,
            model_config_snapshot=policy,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return str(row.id)


def capture(identifier):
    with Session(engine) as db:
        row = db.get(StageRun, UUID(identifier))
        return {
            "stage": row.model_dump(mode="json"),
            "rules": [
                r.model_dump(mode="json")
                for r in db.exec(
                    select(RuleVersion).where(RuleVersion.stage_id == row.id)
                ).all()
            ],
            "candidates": [
                r.model_dump(mode="json")
                for r in db.exec(
                    select(Candidate).where(Candidate.stage_id == row.id)
                ).all()
            ],
            "timings": [
                json.loads(p.read_text())
                for p in (ArtifactStore().directory(identifier) / "node-timings").glob(
                    "*.json"
                )
            ],
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.CRITICAL)
    baseline = json.loads((args.baseline / "report.json").read_text())
    output = ROOT / "artifacts/benchmarks" / f"flask-live-{uuid4()}"
    output.mkdir()
    audits, corpus_hash = initialize(output)
    with Session(engine) as db:
        owner = db.get(AuditRun, UUID(audits["python"])).owner_id
    doc = (ROOT / "system/knowledge/flask-route-shortcuts.md").read_text()
    import_knowledge(
        owner,
        "Flask Python XSS route get post API",
        "framework-api:flask-routing",
        "python",
        doc,
        {
            "api_version": baseline["dependencies"]["codeql/python-all"]["version"],
            "license": "original-summary",
            "trust": "reviewed_official_summary",
        },
    )
    policy = policy_snapshot()
    policy["thinking_mode"] = "disabled"
    report = {
        "scope": "one real framework API family, 12 constructed hidden cases; 3 repetitions per arm are stability, not independent CVEs",
        "dataset_hash": baseline["dataset_hash"],
        "corpus_hash": corpus_hash,
        "knowledge_hash": hashlib.sha256(doc.encode()).hexdigest(),
        "policy": policy,
        "arms": ARMS,
        "generation": [],
        "review": [],
    }
    path = output / "report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print("OUTPUT=" + str(output), flush=True)
    for repetition in range(1, 4):
        for arm, flags in ARMS.items():
            identifier = stage(
                audits["python"],
                "rule",
                {
                    "requirement": "Generate a Python XSS detector extending missing Flask and Blueprint get/post route shortcuts. Ground their registration semantics in retrieved framework API documentation. Preserve pinned CodeQL XSS taint and escaping logic; do not treat arbitrary same-name methods as HTTP routes. Cover all four documented shortcuts and explain baseline gaps. Provide small regression positive and negative fixtures.",
                    "purpose": "vulnerability_detector",
                    "strategy": "new_query",
                },
                {**policy, "rule_experiment": flags},
                "5",
            )
            start = time.perf_counter()
            execute_stage.run(identifier)
            row = {
                "arm": arm,
                "round": repetition,
                "generation_seconds": time.perf_counter() - start,
                **capture(identifier),
            }
            if row["rules"]:
                rule = row["rules"][0]
                pack = output / identifier / "evaluation"
                try:
                    prepare_query(
                        pack,
                        "python",
                        rule["query"],
                        rule["modules"],
                        rule["dependencies"],
                    )
                    start = time.perf_counter()
                    findings = run_query(
                        args.baseline / "database",
                        pack,
                        pack / "result.sarif",
                        pack / "execution.log",
                        baseline["snapshot"],
                    )
                    row["hidden_seconds"] = time.perf_counter() - start
                    row["hidden"] = score(baseline["labels"], findings)
                except Exception as exc:  # noqa: BLE001 - failed requests remain in denominator
                    row["hidden_error"] = {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }
            report["generation"].append(row)
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print(
                arm,
                repetition,
                row["stage"]["status"],
                row.get("hidden", {}).get("counts"),
                flush=True,
            )

    # Review the same actual manual-model CodeQL alerts for each mode.
    from app.adapters.codeql.sarif import parse_sarif

    findings = parse_sarif(args.baseline / "manual_model-3.sarif", baseline["snapshot"])
    archive = output / "review-source.zip"
    with ZipFile(archive, "w") as bundle:
        for file in (args.baseline / "source").glob("*.py"):
            bundle.write(file, file.name)
    with Session(engine) as db:
        review_owner = uuid4()
        db.add(
            User(
                id=review_owner,
                email=f"{review_owner}@benchmark.invalid",
                hashed_password="disabled-research-owner",
                is_active=False,
            )
        )
        db.commit()
        audit = create_run(
            db, review_owner, archive, "framework-review-pilot", "python"
        )
        # The source snapshot matches the actual CodeQL evaluator snapshot.
        if audit.snapshot_hash != baseline["snapshot"]:
            raise ValueError("Review input snapshot differs from CodeQL scan")
        audit.status, audit.findings = "completed", findings
        db.add(audit)
        db.commit()
        audit_id = str(audit.id)
    for repetition in range(1, 4):
        for mode in ("fixed_context", "active_evidence"):
            identifier = stage(
                audit_id,
                "review",
                {"discover": False, "max_steps": 8, "max_context_chars": 60000},
                policy,
                "2",
            )
            start = time.perf_counter()
            if mode == "active_evidence":
                execute_stage.run(identifier)
            else:
                from app.persistence.stage_repository import StageRepository

                repository = StageRepository()
                repository.claim(identifier)
                try:
                    provider = CompatibleModel()
                    provider.bind_stage(identifier, "2")
                    service = ReviewService(identifier, provider)
                    context = service.prepare()
                    context["context"]["tool_policy"] = (
                        "Only the supplied fixed evidence is available in this evaluation. Return final; abstain if insufficient."
                    )
                    response = provider.generate(
                        "review", context["context"], ReviewResponseV2
                    )
                    if response.action != "final":
                        raise ValueError(
                            "fixed-context mode requested unavailable tool"
                        )
                    service.save(
                        {**context, "response": response.model_dump(mode="json")}
                    )
                except Exception as exc:  # noqa: BLE001 - record model/protocol/tool failures
                    repository.update(
                        identifier, status="failed", error=str(exc)[:1000]
                    )
            row = {
                "mode": mode,
                "round": repetition,
                "seconds": time.perf_counter() - start,
                **capture(identifier),
            }
            labels = {
                (r["file"], r["line"]): r["vulnerable"] for r in baseline["labels"]
            }
            row["assessment_scores"] = [
                {
                    "assessment": c["model_assessment"],
                    "vulnerable": labels.get(
                        (c["location"]["file"], c["location"]["line"])
                    ),
                }
                for c in row["candidates"]
            ]
            report["review"].append(row)
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print(mode, repetition, row["stage"]["status"], flush=True)
    print("REPORT_PATH=" + str(path), flush=True)


if __name__ == "__main__":
    main()
