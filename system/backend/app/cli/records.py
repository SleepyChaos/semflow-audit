"""Read persistent evidence and apply explicit stage lifecycle commands."""

import json

from sqlmodel import Session, select

from app.adapters.artifacts import ArtifactStore
from app.adapters.experiment_receipts import execution_record
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, Evidence, StageRun
from app.persistence.workspace import resolve_workspace
from app.runtime.stages import run_stage
from app.services.stage_actions import (
    approve_stage,
    cancel_stage,
    recover_stage,
    retry_stage,
)
from app.services.stage_lifecycle import owned_audit, owned_stage


def inspect_record(identifier, *, evidence=False, logs=False):
    with Session(engine) as session:
        owner_id = resolve_workspace(session).id
        stage = session.get(StageRun, identifier)
        audit = session.get(AuditRun, identifier)
        if stage is not None:
            owned_stage(session, identifier, owner_id)
            data = {"type": "stage", **execution_record(stage)}
            clause = Evidence.stage_id == identifier
            candidates = Candidate.stage_id == identifier
        elif audit is not None:
            owned_audit(session, identifier, owner_id)
            data = {"type": "audit", **execution_record(audit)}
            clause = Evidence.audit_id == identifier
            candidates = Candidate.audit_id == identifier
        else:
            directory = audit_settings.ARTIFACT_ROOT / "runs" / str(identifier)
            path = directory / "execution-receipt.json"
            if not path.is_file():
                raise AuditError("Execution does not exist", code="not_found")
            data = json.loads(path.read_text(encoding="utf-8"))
            if data["owner_id"] != str(owner_id):
                raise AuditError("Execution does not exist", code="not_found")
            data["type"] = "experiment"
            data["input"] = json.loads(
                (directory / "experiment-input.json").read_text(encoding="utf-8")
            )
            # The receipt records history; live child statuses can advance after approval.
            data["current_stages"] = [
                execution_record(owned_stage(session, row["id"], owner_id))
                for row in data["stages"]
            ]
            return data
        data["candidates"] = [
            row.model_dump(mode="json")
            for row in session.exec(select(Candidate).where(candidates)).all()
        ]
        if evidence:
            data["evidence"] = [
                row.model_dump(mode="json")
                for row in session.exec(select(Evidence).where(clause)).all()
            ]
        if logs:
            data["log"] = ArtifactStore().log_tail(str(identifier))
        return data


def stage_action(command, identifier, reason=None):
    with Session(engine) as session:
        owner_id = resolve_workspace(session).id
        if command == "resume":
            row = approve_stage(session, identifier, owner_id, reason)
        elif command == "retry":
            row = retry_stage(session, identifier, owner_id)
        elif command == "cancel":
            row = cancel_stage(session, identifier, owner_id)
        else:
            row = recover_stage(session, identifier, owner_id)
    if command in {"resume", "retry"}:
        row = run_stage(str(row.id), resume=command == "resume")
    return {"type": "stage", **execution_record(row)}


def decide_candidate(identifier, status, reason, evidence_ids):
    from app.contracts.stages import DecisionRequest
    from app.services.candidate_decisions import record_decision

    body = DecisionRequest(status=status, reason=reason, evidence_ids=evidence_ids)
    with Session(engine) as session:
        owner_id = resolve_workspace(session).id
        return record_decision(session, identifier, owner_id, body).model_dump(
            mode="json"
        )
