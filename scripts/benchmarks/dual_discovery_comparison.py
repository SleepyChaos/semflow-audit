"""Small real CodeQL/model comparison; no service startup or exploit replay."""

import argparse
import json
import logging
import time
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.scanner import CodeQLScanner
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.jobs.stages import execute_stage
from app.models import User
from app.persistence.audit_repository import AuditRepository
from app.persistence.stage_models import Candidate, StageRun
from app.services.context_materials import digest, save_json
from app.services.dual_scanning import DualScanService
from app.services.scanning import ScanService
from app.services.uploads import create_run
from app.workflows.dual_scanning import build_dual_scan_graph
from dual_discovery_cases import cases
from sqlmodel import Session, select


def review(audit_id, version):
    with Session(engine) as db:
        stage = StageRun(
            audit_id=audit_id,
            kind="review",
            prompt_version=version,
            inputs={"include_scout": version == "4", "max_steps": 6, "max_batches": 8},
        )
        db.add(stage)
        db.commit()
        db.refresh(stage)
        stage_id = stage.id
    started = time.perf_counter()
    execute_stage.run(str(stage_id))
    with Session(engine) as db:
        stage = db.get(StageRun, stage_id)
        candidates = db.exec(
            select(Candidate).where(Candidate.stage_id == stage_id)
        ).all()
        return {
            "version": version,
            "stage_id": str(stage_id),
            "status": stage.status,
            "error": stage.error,
            "seconds": time.perf_counter() - started,
            "usage": stage.usage,
            "model_calls": stage.model_calls,
            "result": stage.result,
            "candidates": [r.model_dump(mode="json") for r in candidates],
        }


def score(row, case):
    relevant = [
        r
        for r in row["candidates"]
        if r["weakness"] in case["cwes"] and r["location"].get("file") == "app.py"
    ]
    supported = [r for r in relevant if r["model_assessment"] == "supported"]
    return {
        "target_supported": bool(supported),
        "target_result": ("TP" if case["vulnerable"] else "FP")
        if supported
        else ("FN" if case["vulnerable"] else "no_supported_target"),
        "unreviewed": row["result"].get("unreviewed_candidate_ids", []),
        "meaning": "Only target condition evaluated; no_supported_target is not proof of a reviewed true negative. Root correspondence requires inspection of raw reasons.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--complete-entrypoints", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    logging.basicConfig(filename=args.output / "execution.log", level=logging.WARNING)
    owner, material = uuid4(), cases(args.complete_entrypoints)
    with Session(engine) as db:
        db.add(
            User(
                id=owner,
                email=f"dual-{owner}@research.invalid",
                hashed_password="disabled-research",
                is_active=False,
            )
        )
        db.commit()
    # Freeze source and labels before the first call. Labels are evaluator-only.
    protocol = {
        "owner": str(owner),
        "cases": material,
        "case_hash": digest(material),
        "model": audit_settings.AI_MODEL,
        "rounds": args.rounds,
        "complete_entrypoints": args.complete_entrypoints,
        "suite": "python-code-scanning",
        "evaluation_scope": "Six synthetic development cases, three condition pairs; no population/generalization claim",
        "implementation_hashes": {
            str(p): digest(p.read_text())
            for folder in (
                "backend/app/services",
                "backend/app/prompts",
                "backend/app/workflows",
                "backend/app/adapters",
                "backend/app/contracts",
                "backend/app/core",
            )
            for p in Path(folder).rglob("*")
            if p.suffix in {".py", ".txt"}
        },
    }
    save_json(args.output / "protocol.json", protocol)
    report = {
        "protocol": {k: v for k, v in protocol.items() if k != "cases"},
        "audits": [],
        "rows": [],
    }
    for name, case in material.items():
        archive = args.output / f"{name}.zip"
        with ZipFile(archive, "w") as bundle:
            for file, content in case["files"].items():
                bundle.writestr(file, content)
        with Session(engine) as db:
            audit = create_run(
                db,
                owner,
                archive,
                "dual-development-" + name,
                "python",
                dual_engine=True,
            )
            audit_id = audit.id
        repository = AuditRepository()
        repository.claim(str(audit_id))
        started = time.perf_counter()
        service = DualScanService(
            ScanService(repository, ArtifactStore(), CodeQLScanner())
        )
        build_dual_scan_graph(service).invoke({"run_id": str(audit_id)})
        audit = repository.get(str(audit_id))
        report["audits"].append(
            {
                "case": name,
                "id": str(audit_id),
                "seconds": time.perf_counter() - started,
                "static_findings": audit.findings,
                "coverage": audit.coverage,
                "status": audit.status,
            }
        )
        for number in range(args.rounds):
            # Alternate order; runs share normal caches and a small project snapshot.
            for version in ["2", "4"] if number % 2 == 0 else ["4", "2"]:
                row = review(audit_id, version)
                row.update(case=name, round=number + 1, evaluation=score(row, case))
                report["rows"].append(row)
                save_json(args.output / "report.json", report)
                print(
                    json.dumps(
                        {
                            "case": name,
                            "version": version,
                            "status": row["status"],
                            "target": row["evaluation"]["target_result"],
                            "seconds": round(row["seconds"], 2),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    report["frozen_inputs_verified"] = (
        digest(cases(args.complete_entrypoints)) == protocol["case_hash"]
    )
    report["implementation_verified"] = all(
        digest(Path(p).read_text()) == h
        for p, h in protocol["implementation_hashes"].items()
    )
    save_json(args.output / "report.json", report)
    print("REPORT=" + str(args.output / "report.json"), flush=True)


if __name__ == "__main__":
    main()
