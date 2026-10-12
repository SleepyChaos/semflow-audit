"""Additional matched prototype: real dev execution enters bounded generation loop."""

import argparse
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from uuid import UUID, uuid4

from sqlmodel import Session, select
from app.core.db import engine
from app.jobs.stages import execute_stage
from app.persistence.stage_models import StageRun
from app.persistence.knowledge_models import RuleVersion


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("main_output", type=Path)
    parser.add_argument("framework_output", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.CRITICAL)
    output = args.main_output.parent / ("dev-feedback-ablation-" + str(uuid4()))
    output.mkdir()
    (output / "records").mkdir()
    main_rows = [
        json.loads(path.read_text())
        for path in (args.main_output / "records").glob("*.json")
    ]
    framework_rows = json.loads((args.framework_output / "report.json").read_text())[
        "records"
    ]
    sources = [
        ("K_spec_routed_dev", row) for row in main_rows if row["arm"] == "F_spec_routed"
    ] + [
        ("L_framework_grounded_dev", row)
        for row in framework_rows
        if row["arm"] == "I_spec_grounded"
    ]
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "scope": "Supplementary real dev-execution feedback; same case/prompt/model/policy as F or I, 3 repetitions; preserve all failures; no independent fixtures passed to generation",
                "references": [
                    str(args.main_output.resolve()),
                    str(args.framework_output.resolve()),
                ],
                "requests": len(sources),
                "workers": 2,
                "stage_ids": [row["stage"]["id"] for _, row in sources],
            },
            indent=2,
        )
    )
    print("OUTPUT=" + str(output), flush=True)

    def run(arm, reference):
        original = reference["stage"]
        policy = {**original["model_config_snapshot"]}
        policy["rule_experiment"] = {**policy["rule_experiment"], "execute_dev": True}
        with Session(engine) as db:
            stage = StageRun(
                audit_id=UUID(original["audit_id"]),
                kind="rule",
                inputs=original["inputs"],
                prompt_version=original["prompt_version"],
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
            rules = db.exec(
                select(RuleVersion).where(RuleVersion.stage_id == identifier)
            ).all()
            record = {
                "arm": arm,
                "case": reference["case"],
                "round": reference["round"],
                "generation_seconds": time.perf_counter() - start,
                "stage": stage.model_dump(mode="json"),
                "rules": [rule.model_dump(mode="json") for rule in rules],
            }
        (output / "records" / f"{identifier}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2)
        )
        print(arm, record["case"], record["round"], stage.status, flush=True)
        return record

    rows = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, arm, row) for arm, row in sources]
        for future in as_completed(futures):
            rows.append(future.result())
    (output / "report.json").write_text(
        json.dumps(
            {
                "records": rows,
                "manifest": json.loads((output / "manifest.json").read_text()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
