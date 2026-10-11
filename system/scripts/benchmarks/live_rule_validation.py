"""Resume only evaluator-inspected benchmark drafts; never publish a rule."""

import json
import sys
import time
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "system/backend"))
from app.adapters.codeql.custom import prepare_query, run_query
from app.adapters.snapshot import snapshot_digest
from app.core.db import engine
from app.jobs.stages import execute_stage
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import StageRun
from sqlmodel import Session

APPROVED = {
    "9ea44c60-2238-4097-984d-0056690e2197": "9c77ffac4ce5f39f2ff27a9b1a659c731618a9a29d87170ee064a065357fc4c9",
    "8c2c87a1-d381-47c2-a170-6392e955ac5c": "e44a6f28714d2ef4c4cf4598e5b16c4b7e0f664ecd4dfd7f82cd56ccf1a9de71",
    "67fb9690-9bad-428f-921b-647b430d2ad0": "fe9cd44364e0161fa80ac1eeb9caf7aa70323ea55bc57e89a3f646d448760eab",
}


def main():
    directory = next((ROOT / "artifacts/benchmarks").glob("live-model-*"))
    holdout = next((ROOT / "artifacts/benchmarks").glob("rule-holdout-*"))
    results = []
    for identifier, digest in APPROVED.items():
        with Session(engine) as db:
            rule = db.get(RuleVersion, UUID(identifier))
            stage = db.get(StageRun, rule.stage_id)
            if digest and rule.query_hash != digest:
                raise RuntimeError("Inspected rule changed")
            if stage.status != "awaiting_confirmation" or rule.published_at:
                raise RuntimeError(
                    "Not an unpublished benchmark draft awaiting inspection"
                )
            if str(rule.owner_id) != "ca81e851-bd1b-4e1e-ae03-18af6e11d1a3":
                raise RuntimeError("Not the isolated research owner")
            rule.fixtures_approved = True
            rule.fixture_approval_reason = "Research evaluator inspected name-matching query and exact positive/negative source locations. Approval is limited to syntax review anchors, not built-in resolution or taint vulnerability accuracy. No publication authorization."
            stage.status = "queued"
            db.add(rule)
            db.add(stage)
            db.commit()
            stage_id = str(stage.id)
        start = time.perf_counter()
        execute_stage.run(stage_id, True)
        with Session(engine) as db:
            rule = db.get(RuleVersion, UUID(identifier))
            stage = db.get(StageRun, rule.stage_id)
            record = {
                "rule": rule.model_dump(mode="json"),
                "stage_status": stage.status,
                "error": stage.error,
                "validation_seconds": time.perf_counter() - start,
            }
            db.expunge(rule)
        pack = directory / ("holdout-" + identifier)
        prepare_query(pack, rule.language, rule.query, rule.modules, rule.dependencies)
        start = time.perf_counter()
        findings = run_query(
            holdout / "database",
            pack,
            pack / "holdout.sarif",
            pack / "execution.log",
            snapshot_digest(holdout / "source"),
        )
        record["holdout_seconds"] = time.perf_counter() - start
        record["holdout_locations"] = [
            loc for finding in findings for loc in finding["locations"]
        ]
        record["holdout_meaning"] = (
            "Independent 8-case review-anchor coverage. Locations are not vulnerability predictions; aliases missed and constant/shadowed names matched."
        )
        results.append(record)
        (directory / "rule-validation.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2)
        )
        print(
            identifier,
            stage.status,
            rule.validation.get("status"),
            len(findings),
            flush=True,
        )


if __name__ == "__main__":
    main()
