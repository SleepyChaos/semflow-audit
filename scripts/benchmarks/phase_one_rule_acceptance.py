"""Research evaluator approval for three inspected anchor drafts; no publication."""

import json
from pathlib import Path
from uuid import UUID

from app.core.db import engine
from app.jobs.stages import execute_stage
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import StageRun
from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[2]
APPROVED = {
    "89b64108-87c7-4697-bed6-1361b53966ae": "8c7e712f68b4bcc9f27d6ff141c05eb6f37d9e06e6569bc3309fc6eca23aeb7c",
    "39990c12-5ff9-4f59-bff2-0b25cd5a74c0": "72a93873a54384926e87acba3e4f75da2a12ac2d9a3430aea35b44208b8e5a9d",
    "f3350828-e2a5-4896-9a2e-1e029703d3fc": "fec6c6f5339c28f8df85ca1f3583f1ada40c0dc90cb23ba530b71962a41ee7a2",
}


def main():
    output = (
        next((ROOT / "artifacts/benchmarks").glob("phase-one-*"))
        / "rule-acceptance.json"
    )
    records = []
    for identifier, digest in APPROVED.items():
        with Session(engine) as db:
            rule = db.get(RuleVersion, UUID(identifier))
            stage = db.get(StageRun, rule.stage_id)
            if (
                rule.query_hash != digest
                or str(rule.owner_id) != "ca81e851-bd1b-4e1e-ae03-18af6e11d1a3"
                or stage.status != "awaiting_confirmation"
            ):
                raise SystemExit("Inspected unpublished research draft changed")
            rule.fixtures_approved = True
            rule.fixture_approval_reason = "Research evaluator inspected complete name-based anchor query and exact generated positive/negative locations. This only approves review-anchor regression semantics, not vulnerability accuracy. No rule publication."
            stage.status = "queued"
            db.add(rule)
            db.add(stage)
            db.commit()
            stage_id = str(stage.id)
        execute_stage.run(stage_id, True)
        with Session(engine) as db:
            rule = db.get(RuleVersion, UUID(identifier))
            stage = db.get(StageRun, rule.stage_id)
            records.append(
                {
                    "rule": rule.model_dump(mode="json"),
                    "stage_status": stage.status,
                    "error": stage.error,
                    "usage_after_resume": stage.usage,
                    "call_count_after_resume": len(stage.model_calls),
                }
            )
        output.write_text(json.dumps(records, ensure_ascii=False, indent=2))
        print(identifier, stage.status, rule.status, flush=True)


if __name__ == "__main__":
    main()
