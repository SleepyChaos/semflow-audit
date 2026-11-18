"""Resolve platform candidate ownership and convert it to the public review retry."""

from uuid import UUID

from semflow_contracts.errors import ResearchError
from semflow_research.public.review_continuation import assemble
from sqlmodel import select

from app.domain.audit import AuditError
from app.persistence.stage_models import Candidate, StageRun
from app.research_bridge.models import ResearchBinding


def prior_target(session, audit, candidate_id):
    row = session.get(Candidate, UUID(str(candidate_id)))
    if row is None or row.audit_id != audit.id:
        raise AuditError("Selected candidate does not belong to this audit")
    stage = session.get(StageRun, row.stage_id)
    if stage is None or stage.kind != "review" or stage.status != "completed":
        raise AuditError("Select a candidate from a completed review")
    if row.status in {"confirmed", "excluded"} or row.model_assessment not in {
        "pending",
        "insufficient",
        "unknown",
    }:
        raise AuditError("Selected candidate is already resolved")
    binding = session.exec(
        select(ResearchBinding).where(ResearchBinding.stage_id == stage.id)
    ).first()
    if (
        binding is None
        or binding.manifest is None
        or binding.legacy_source_digest != audit.snapshot_hash
    ):
        raise AuditError(
            "Prior review evidence is unavailable for this source snapshot"
        )
    prefix = f"{binding.execution_id}/"
    source_ids = [
        UUID(key.removeprefix(prefix))
        for key, value in binding.entity_map.items()
        if key.startswith(prefix) and value == str(row.id)
    ]
    if len(source_ids) != 1:
        raise AuditError("Prior review candidate identity is unavailable")
    return binding, source_ids[0]


def freeze_continuation(session, binding, stage, audit, root):
    previous, source_id = prior_target(
        session, audit, stage.inputs["continuation_candidate_id"]
    )
    try:
        spec = assemble(
            previous.execution_id,
            source_id,
            root=root,
            execution_id_override=binding.execution_id,
        )
    except ResearchError as exc:
        raise AuditError(str(exc), code=exc.code) from exc
    selected = {str(source_id), *map(str, spec.inputs.evidence.entity_ids)}
    binding.entity_map = {
        key: value
        for key, value in previous.entity_map.items()
        if key.startswith(f"{previous.execution_id}/")
        and key.split("/", 1)[1] in selected
    }
    return spec
