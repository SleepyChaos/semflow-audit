"""Exploratory two-factor library-corpus and thinking-disabled control."""

import json
from pathlib import Path
from uuid import uuid4

from app.adapters.ai.policy import policy_snapshot
from app.adapters.artifacts import ArtifactStore
from app.core.db import engine
from app.jobs.stages import execute_stage
from app.models import User
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import StageRun
from sqlmodel import Session, select

from scripts.benchmarks import live_model
from scripts.curate_codeql_library import main as import_library

ROOT = Path(__file__).resolve().parents[2]


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
    output = ROOT / "artifacts/benchmarks" / ("library-control-" + str(uuid4()))
    output.mkdir()
    owner = uuid4()
    with Session(engine) as db:
        db.add(
            User(
                id=owner,
                email=f"{owner}@benchmark.invalid",
                hashed_password="disabled-research-owner",
                is_active=False,
            )
        )
        db.commit()
    import_library(owner)
    live_model.OUTPUT = output
    source = ArtifactStore().directory(reference["stage"]["audit_id"]) / "source"
    audit_id, scan_seconds = live_model.new_audit(
        owner, source, "library-control", "python"
    )
    records = {
        "scope": "Exploratory: corpus and thinking both changed; not a RAG causal ablation",
        "scan_seconds": scan_seconds,
        "stages": [],
    }
    for number in range(1, 4):
        policy = policy_snapshot()
        policy["thinking_mode"] = "disabled"
        with Session(engine) as db:
            stage = StageRun(
                audit_id=audit_id,
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
        records["stages"].append(record)
        (output / "report.json").write_text(
            json.dumps(records, ensure_ascii=False, indent=2)
        )
        print(number, stage.status, stage.error, flush=True)
    print("REPORT_PATH=" + str(output / "report.json"), flush=True)


if __name__ == "__main__":
    main()
