"""V2 real-provider comparisons; preserve all failures; no GUI or auto publication."""

import json
import time
from pathlib import Path
from uuid import UUID, uuid4

from app.adapters.ai.policy import policy_snapshot
from app.core.db import engine
from app.jobs.stages import execute_stage
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import Candidate, RepairRecord, StageRun
from app.services.rule_holdouts import catalog
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[2]


def main():
    baseline = json.loads(
        next(
            (ROOT / "artifacts/benchmarks").glob("live-model-*/report.json")
        ).read_text()
    )
    output = ROOT / "artifacts/benchmarks" / ("phase-one-" + str(uuid4()))
    output.mkdir()
    results = {
        "scope": "V2 fixed-config small calibration; repeat runs not independent samples",
        "stages": [],
    }

    def run(audit_id, kind, inputs, case, round_number, budget=6000):
        policy = policy_snapshot()
        policy["budgets"][kind] = budget
        with Session(engine) as db:
            stage = StageRun(
                audit_id=UUID(audit_id),
                kind=kind,
                inputs=inputs,
                prompt_version="2" if kind in {"rule", "review"} else "1",
                model_config_snapshot=policy,
            )
            db.add(stage)
            db.commit()
            db.refresh(stage)
            identifier = stage.id
        start = time.perf_counter()
        execute_stage.run(str(identifier))
        with Session(engine) as db:
            stage = db.get(StageRun, identifier)
            record = {
                "case": case,
                "round": round_number,
                "budget": budget,
                "seconds": time.perf_counter() - start,
                "stage": stage.model_dump(mode="json"),
            }
            record["candidates"] = [
                row.model_dump(mode="json")
                for row in db.exec(
                    select(Candidate).where(Candidate.stage_id == identifier)
                ).all()
            ]
            record["rules"] = [
                row.model_dump(mode="json")
                for row in db.exec(
                    select(RuleVersion).where(RuleVersion.stage_id == identifier)
                ).all()
            ]
            repair = db.exec(
                select(RepairRecord).where(RepairRecord.stage_id == identifier)
            ).first()
            if repair:
                record["repair"] = repair.model_dump(mode="json")
        results["stages"].append(record)
        (output / "report.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2)
        )
        print(case, round_number, budget, stage.status, stage.error, flush=True)

    py = baseline["audits"][0]["id"]
    js = baseline["audits"][1]["id"]
    corrected = next(
        s["audit_id"] for s in baseline["stages"] if s["case"] == "shadowed_json.js"
    )
    for budget in (6000, 12000):
        for number in range(1, 4):
            for audit, file in [
                (py, "shadowed_function.py"),
                (corrected, "shadowed_json.js"),
            ]:
                run(
                    audit,
                    "review",
                    {
                        "paths": [file],
                        "discover": True,
                        "max_steps": 8,
                        "max_context_chars": 60000,
                    },
                    file,
                    number,
                    budget,
                )
    repair = next(s for s in baseline["stages"] if s["case"] == "javascript-pp")
    candidate_id = repair.get("repair", {}).get("candidate_ids")
    if not candidate_id:
        with Session(engine) as db:
            candidate_id = [
                str(
                    db.exec(
                        select(Candidate).where(
                            Candidate.audit_id == UUID(repair["audit_id"]),
                            Candidate.status == "confirmed",
                        )
                    )
                    .one()
                    .id
                )
            ]
    for number in range(1, 4):
        run(
            repair["audit_id"],
            "repair",
            {
                "candidate_ids": candidate_id,
                "allowed_paths": ["merge.js"],
                "validation_profile": "javascript_test",
                "rescan": True,
            },
            "javascript-pp",
            number,
        )
    for entry in catalog():
        for number in range(1, 4):
            requirement = f"Generate a fixed-version CodeQL {entry['purpose']} for {entry['language']} {entry['operation']}. Cite retrieved API sources, explain actual baseline coverage limitations. Direct eval anchors must match unqualified eval calls by name; SQL anchors inventory database execution, XSS anchors inventory HTTP HTML response operations. Vulnerability detectors require user-input dataflow and genuine sink resolution with safe inputs excluded. Do not treat anchors as vulnerability proof."
            run(
                py if entry["language"] == "python" else js,
                "rule",
                {
                    "requirement": requirement,
                    "purpose": entry["purpose"],
                    "holdout_id": entry["id"],
                    "strategy": "new_query",
                },
                entry["id"],
                number,
            )
    print("REPORT_PATH=" + str(output / "report.json"), flush=True)


if __name__ == "__main__":
    main()
