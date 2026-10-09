"""Actual v1/v2 repair pilot; hidden module oracles run only after generation."""

import argparse
import json
from uuid import UUID

from app.adapters.artifacts import ArtifactStore
from app.core.db import engine
from app.persistence.stage_models import Candidate, RepairRecord, StageRun
from app.services.evidence import EvidenceService
from app.services.repair import RepairService
from app.workflows.repair import build_repair_graph
from sqlmodel import Session, select

from scripts.benchmarks.formal_freeze import OUTPUT, save
from scripts.benchmarks.formal_repair_oracle import CASE, evaluate
from scripts.benchmarks.formal_runtime import (
    checkpoint_stage,
    new_stage,
    register_audit,
)


def target(audit):
    path = OUTPUT / "repair/target.json"
    if path.exists():
        return json.loads(path.read_text())["candidate_id"]
    with Session(engine) as db:
        stage = StageRun(
            audit_id=UUID(audit), kind="calibration_target", status="completed"
        )
        db.add(stage)
        db.commit()
        db.refresh(stage)
        stage_id = str(stage.id)
    material = EvidenceService(audit, stage_id, []).read("lib/util.js", 480, 537)
    with Session(engine) as db:
        candidate = Candidate(
            audit_id=UUID(audit),
            stage_id=UUID(stage_id),
            origin="evaluator_calibration",
            status="confirmed",
            title="Incomplete interface-name sanitization",
            description="Network interface identifiers pass through sanitizeShellString before interpolation into system command strings. Double quotes, newline and tab characters are not removed by this implementation and can alter command token boundaries. Preserve the established return API and ordinary interface names; harden this boundary without deleting the exported function.",
            weakness="CWE-78",
            location={"file": "lib/util.js", "line": 488},
            evidence_ids=[material["id"]],
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        identifier = str(candidate.id)
    save(
        path,
        {
            "candidate_id": identifier,
            "scope": "fixed evaluator description, not audit-driven end-to-end repair or human confirmation",
        },
    )
    return identifier


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=1)
    args = parser.parse_args()
    audit = register_audit(CASE)
    candidate = target(audit)
    for number in range(1, args.rounds + 1):
        for version in ["1", "2"] if number % 2 else ["2", "1"]:
            directory = OUTPUT / "repair" / f"v{version}-round-{number}"
            row = checkpoint_stage(
                directory / "generation.json",
                lambda version=version: new_stage(
                    audit,
                    "repair",
                    version,
                    {
                        "candidate_ids": [candidate],
                        "allowed_paths": ["lib/util.js"],
                        "validation_profile": "syntax",
                        "rescan": False,
                    },
                ),
                RepairService,
                build_repair_graph,
            )
            scored = directory / "scored.json"
            if scored.exists():
                continue
            with Session(engine) as db:
                record = db.exec(
                    select(RepairRecord).where(
                        RepairRecord.stage_id == UUID(row["stage_id"])
                    )
                ).first()
            checks = {"status": "unknown", "reason": "no_applied_patch"}
            if record:
                root = ArtifactStore().directory(row["stage_id"])
                if version == "1":
                    workspace = root / "workspace"
                else:
                    attempts = record.validation.get("semantic_scope", {}).get(
                        "attempts"
                    )
                    workspace = root / f"attempt-{attempts}/workspace"
                if workspace.is_dir():
                    checks = evaluate(directory / "hidden-evaluation", workspace)
            save(
                scored,
                {
                    "version": version,
                    "round": number,
                    "generation": row,
                    "oracle": checks,
                    "formal_gold": False,
                    "interpretation": "bounded derived-oracle pilot, not benchmark security repair success rate",
                },
            )
            print(
                json.dumps(
                    {
                        "version": version,
                        "round": number,
                        "oracle_status": checks["status"],
                        "joint_pass": checks.get("joint_pass"),
                    }
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
