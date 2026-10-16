"""Recovery exports inherited hypotheses without foreign audit contamination."""

from uuid import uuid4

from app.core.db import engine
from app.persistence.stage_models import StageRun
from scripts.benchmarks.formal_runtime import stage_record
from scripts.benchmarks.realvuln_resume import inherited_candidates
from sqlmodel import Session

from tests.test_dual_discovery import run_scout


def test_candidate_receipt_keeps_old_evidence_and_rejects_foreign_audit(
    pipeline_context,
):
    import pytest

    old = run_scout(pipeline_context, version="4", max_units=1)
    original = stage_record(old.stage_id, 0)
    assert original["candidates"]
    with Session(engine) as db:
        new = StageRun(
            audit_id=old.stage.audit_id,
            kind="scout",
            result={"source_stage_ids": [old.stage_id]},
        )
        db.add(new)
        db.commit()
        db.refresh(new)
        new_id = str(new.id)
    record = stage_record(new_id, 0)
    exported = inherited_candidates(record)
    assert exported["candidates"][0]["id"] == original["candidates"][0]["id"]
    assert (
        exported["candidates"][0]["evidence_ids"]
        == original["candidates"][0]["evidence_ids"]
    )
    assert stage_record(old.stage_id, 0) == original
    record["stage"]["audit_id"] = str(uuid4())
    with pytest.raises(RuntimeError, match="crosses audit"):
        inherited_candidates(record)
