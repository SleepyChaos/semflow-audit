"""Explicit experimental thinking-disabled group; does not edit default configuration."""

import json
from pathlib import Path
from uuid import UUID, uuid4

from app.adapters.ai.policy import policy_snapshot
from app.core.db import engine
from app.jobs.stages import execute_stage
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import StageRun
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[3]


def main():
    baseline = json.loads(
        next(
            (ROOT / "artifacts/benchmarks").glob("phase-one-*/report.json")
        ).read_text()
    )
    reference = next(
        row
        for row in baseline["stages"]
        if row["case"] == "python-eval-vulnerability_detector-v1"
    )
    output = ROOT / "artifacts/benchmarks" / ("thinking-control-" + str(uuid4()))
    output.mkdir()
    records = []
    for number in range(1, 4):
        policy = policy_snapshot()
        policy["thinking_mode"] = "disabled"
        with Session(engine) as db:
            stage = StageRun(
                audit_id=UUID(reference["stage"]["audit_id"]),
                kind="rule",
                inputs=reference["stage"]["inputs"],
                prompt_version="2",
                model_config_snapshot=policy,
            )
            db.add(stage)
            db.commit()
            db.refresh(stage)
            identifier = stage.id
        execute_stage.run(str(identifier))
        with Session(engine) as db:
            stage = db.get(StageRun, identifier)
            record = {
                "round": number,
                "stage": stage.model_dump(mode="json"),
                "rules": [
                    r.model_dump(mode="json")
                    for r in db.exec(
                        select(RuleVersion).where(RuleVersion.stage_id == identifier)
                    ).all()
                ],
            }
        records.append(record)
        (output / "report.json").write_text(
            json.dumps(records, ensure_ascii=False, indent=2)
        )
        print(number, stage.status, stage.error, flush=True)


if __name__ == "__main__":
    main()
