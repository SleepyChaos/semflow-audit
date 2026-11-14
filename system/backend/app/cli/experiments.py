"""Sequential experiment execution; scores and evaluator secrets stay elsewhere."""

import logging
import time
from uuid import uuid4

from sqlmodel import Session

from app.adapters.ai.experiment_policy import frozen_policy
from app.adapters.experiment_receipts import (
    ExperimentReceipt,
    execution_record,
    implementation_stamp,
)
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.domain.audit import AuditError
from app.models import get_datetime_utc
from app.persistence.workspace import resolve_workspace
from app.runtime.scans import run_scan
from app.runtime.stages import run_stage
from app.services.stage_lifecycle import create_stage_run, owned_audit
from app.services.uploads import create_run

logger = logging.getLogger(__name__)


def prepare_audit(sample, owner_id):
    with Session(engine) as session:
        if sample.audit_id:
            return owned_audit(session, sample.audit_id, owner_id)
        if sample.archive.suffix.lower() != ".zip" or not sample.archive.is_file():
            raise AuditError("The sample archive must be an existing ZIP file")
        if sample.archive.stat().st_size > audit_settings.UPLOAD_LIMIT:
            raise AuditError("Sample archive exceeds UPLOAD_LIMIT")
        return create_run(
            session,
            owner_id,
            sample.archive,
            sample.id,
            sample.language,
            dual_engine=sample.dual_engine,
        )


def run_sample(sample, name: str, repetition: int, stamp: dict) -> dict:
    with Session(engine) as session:
        owner_id = resolve_workspace(session).id
    identifier = str(uuid4())
    receipt = ExperimentReceipt(identifier)
    logger.info(
        "Experiment %s sample=%s repetition=%s run_id=%s",
        name,
        sample.id,
        repetition,
        identifier,
    )
    receipt.start(
        {
            "schema_version": 1,
            "experiment": name,
            "sample": sample.model_dump(mode="json"),
            "repetition": repetition,
            "owner_id": str(owner_id),
            "implementation": stamp,
            "created_at": get_datetime_utc().isoformat(),
        }
    )
    result = {
        "schema_version": 1,
        "run_id": identifier,
        "experiment": name,
        "sample_id": sample.id,
        "repetition": repetition,
        "owner_id": str(owner_id),
        "status": "running",
        "audit_id": None,
        "stages": [],
        "not_evaluated_stages": len(sample.stages),
        "artifacts": str(receipt.directory),
    }
    began = time.perf_counter()
    receipt.save(result)
    try:
        audit = prepare_audit(sample, owner_id)
        result["audit_id"] = str(audit.id)
        receipt.event(
            "audit_registered",
            {"audit_id": str(audit.id), "snapshot_hash": audit.snapshot_hash},
        )
        receipt.save(result)
        if not sample.audit_id:
            audit = run_scan(str(audit.id))
        result["scan"] = execution_record(audit)
        if audit.status != "completed":
            result["status"] = (
                audit.status if audit.status in {"failed", "cancelled"} else "blocked"
            )
            return result
        for index, spec in enumerate(sample.stages):
            with Session(engine) as session:
                stage = create_stage_run(
                    session,
                    audit.id,
                    owner_id,
                    spec.kind,
                    spec.inputs,
                    prompt_version=spec.prompt_version,
                    policy=frozen_policy(spec),
                )
            result["stages"].append(execution_record(stage))
            logger.info("Stage %s kind=%s", stage.id, stage.kind)
            receipt.event(
                "stage_registered",
                {"stage_id": str(stage.id), "index": index, "kind": stage.kind},
            )
            receipt.save(result)
            stage = run_stage(str(stage.id))
            result["stages"][-1] = execution_record(stage)
            result["not_evaluated_stages"] = len(sample.stages) - index - 1
            receipt.event(
                "stage_finished", {"stage_id": str(stage.id), "status": stage.status}
            )
            receipt.save(result)
            if stage.status != "completed":
                result["status"] = stage.status
                return result
        result["status"] = "completed"
    except KeyboardInterrupt:
        result["status"] = "interrupted"
        receipt.event(
            "interrupted",
            {"meaning": "Use inspect; do not blindly replay external calls"},
        )
        raise
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "code": getattr(exc, "code", "internal_error"),
        }
    finally:
        result["wall_seconds"] = time.perf_counter() - began
        receipt.event(
            "execution_finished",
            {"status": result["status"], "wall_seconds": result["wall_seconds"]},
        )
        receipt.save(result)
    return result


def execute_plan(plan, selected: str | None = None) -> dict:
    samples = [
        sample for sample in plan.samples if selected is None or sample.id == selected
    ]
    if not samples:
        raise AuditError("Sample ID does not exist in this plan")
    from app.runtime.checkpoints import stage_checkpoints

    with stage_checkpoints() as saver:
        saver.setup()
    stamp, results = implementation_stamp(), []
    for repetition in range(1, plan.repetitions + 1):
        for sample in samples:
            results.append(run_sample(sample, plan.name, repetition, stamp))
    counts = {}
    for row in results:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {
        "experiment": plan.name,
        "counts": counts,
        "runs": results,
        "total": len(results),
    }
