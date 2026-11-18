"""Idempotent discovery projection; platform owns presentation and human status."""

from uuid import UUID, uuid5

from semflow_contracts.results import ResultEnvelope
from semflow_research.public.discovery_results import read_result
from sqlmodel import select

from app.domain.audit import AuditError
from app.models import get_datetime_utc
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, Evidence, StageRun
from app.research_bridge.protocol import verify_receipt


def project(session, binding, result, *, root):
    # WIRE-RECV:research.result — peers: discovery_outputs.export and execution.execute.
    # AGENT: completed describes execution, not confirmation. Convert only the
    # platform view; preserve the original manifest, producer and source hashes.
    result = ResultEnvelope.model_validate_json(result.model_dump_json())
    stage = session.exec(
        select(StageRun).where(StageRun.id == binding.stage_id).with_for_update()
    ).one()
    result = verify_receipt(binding, session.get(AuditRun, stage.audit_id), result)
    if result.execution_id != binding.execution_id or result.module != "discovery":
        raise AuditError("科研收据与平台绑定不一致", code="identity_error")
    if binding.manifest is not None:
        if binding.manifest != result.manifest.model_dump(mode="json"):
            raise AuditError("已投影执行不可替换清单", code="integrity_error")
        return stage
    ids = dict(binding.entity_map)
    inherited = set(ids)
    raw, calls, usage = {}, [], {}
    if result.result is not None:
        view = read_result(result.execution_id, root=root)
        for row in (*view.evidence, *view.candidates):
            identifier = getattr(row, "evidence_id", None) or row.candidate_id
            key = f"{row.execution_id}/{identifier}"
            if key not in ids:
                ids[key] = str(uuid5(stage.id, key))
        simple_ids = {key.split("/", 1)[1]: value for key, value in ids.items()}
        assessments = {
            row.candidate_ref.entity_id: row.conclusion for row in view.assessments
        }
        findings = {row.finding_id: row for row in view.findings}
        for row in view.evidence:
            if f"{row.execution_id}/{row.evidence_id}" in inherited:
                existing = session.get(
                    Evidence, UUID(ids[f"{row.execution_id}/{row.evidence_id}"])
                )
                if (
                    existing is None
                    or existing.audit_id != stage.audit_id
                    or existing.digest != row.digest
                    or existing.content != view.content[row.evidence_id]
                ):
                    raise AuditError("继承的证据投影发生变化", code="integrity_error")
                continue
            loc = row.location
            identifier = uuid5(stage.id, f"{row.execution_id}/{row.evidence_id}")
            if session.get(Evidence, identifier) is not None:
                raise AuditError(
                    "投影目标证据已存在但无提交清单", code="integrity_error"
                )
            session.add(
                Evidence(
                    id=identifier,
                    stage_id=stage.id,
                    audit_id=stage.audit_id,
                    kind=row.kind,
                    snapshot_hash=binding.legacy_source_digest,
                    digest=row.digest,
                    content=view.content[row.evidence_id],
                    reference={
                        "file": loc.path,
                        "start_line": loc.start_line,
                        "end_line": loc.end_line,
                    }
                    if loc
                    else {"research_evidence": str(row.evidence_id)},
                )
            )
        for row in view.candidates:
            if f"{row.execution_id}/{row.candidate_id}" in inherited:
                existing = session.get(
                    Candidate, UUID(ids[f"{row.execution_id}/{row.candidate_id}"])
                )
                if existing is None or existing.audit_id != stage.audit_id:
                    raise AuditError("继承候选不属于当前审计", code="identity_error")
                continue  # Preserve any platform human decision on the original.
            evidence_ids = [
                ids[f"{ref.execution_id}/{ref.entity_id}"] for ref in row.evidence_refs
            ]
            session.add(
                Candidate(
                    id=uuid5(stage.id, f"{row.execution_id}/{row.candidate_id}"),
                    audit_id=stage.audit_id,
                    stage_id=stage.id,
                    origin="static" if row.origin == "codeql" else "ai",
                    static_finding_id=findings[row.static_finding_ref.entity_id].raw_id
                    if row.static_finding_ref
                    else None,
                    title=row.title,
                    description=row.description,
                    status="pending",
                    model_assessment=assessments.get(row.candidate_id, "unknown"),
                    evidence_ids=evidence_ids,
                    identity_key=row.identity_key,
                    weakness=row.weakness,
                    novelty="baseline" if row.origin == "codeql" else "unverified",
                    location={
                        "file": row.primary_location.path,
                        "line": row.primary_location.start_line,
                        "end_line": row.primary_location.end_line,
                    },
                    related_target=ids.get(
                        f"{row.derived_from.execution_id}/{row.derived_from.entity_id}",
                    )
                    if row.derived_from
                    else None,
                )
            )
        if view.trace is not None:
            raw = translate_view(
                view.trace.state,
                simple_ids,
                view.trace.source_digest,
                binding.legacy_source_digest,
            )
            calls = translate_view(
                list(view.trace.model_calls),
                simple_ids,
                view.trace.source_digest,
                binding.legacy_source_digest,
            )
            usage = view.trace.usage
            if stage.kind == "review" and raw.get("pool") is not None:
                from app.presentation.discovery import save_review_materials

                save_review_materials(stage, raw["pool"])
        if view.review_report is not None:
            # Peer: public.discovery_results. Preserve the scientific report ID
            # and map displayed candidate/evidence IDs like the existing trace.
            raw["candidate_review_attempts"] = translate_view(
                [row.model_dump(mode="json") for row in view.review_report.records],
                simple_ids,
                view.review_report.source_digest,
                binding.legacy_source_digest,
            )
        if stage.kind == "scout" and view.project_map is not None:
            from app.presentation.discovery import save_scout_materials

            save_scout_materials(
                stage,
                translate_view(
                    view.project_map,
                    simple_ids,
                    view.trace.source_digest,
                    binding.legacy_source_digest,
                ),
            )
    if stage.status != "cancelled":
        stage.status = {
            "completed": "completed",
            "failed": "failed",
            "cancelled": "cancelled",
            "interrupted": "failed",
            "awaiting_input": "awaiting_confirmation",
        }[result.execution_status]
        stage.phase = (
            ("review_ready" if stage.kind == "review" else "hypotheses_ready")
            if stage.status == "completed"
            else stage.status
        )
        stage.error = result.failure.message if result.failure else None
    stage.result = {
        **raw,
        "research_receipt": {
            "execution_id": str(result.execution_id),
            "manifest": result.manifest.model_dump(mode="json"),
            "source_digest": binding.request["source"]["tree_sha256"],
            "legacy_source_digest": binding.legacy_source_digest,
        },
    }
    stage.usage, stage.model_calls = usage, calls
    stage.model = binding.request.get("model", {}).get("model")
    stage.updated_at = get_datetime_utc()
    binding.entity_map, binding.manifest = ids, result.manifest.model_dump(mode="json")
    session.add(stage)
    session.add(binding)
    session.commit()
    session.refresh(stage)
    return stage


def translate_view(value, identifiers, source_digest, legacy_digest):
    """Only this compatibility view translates IDs and the two hash algorithms."""
    if isinstance(value, dict):
        return {
            key: translate_view(item, identifiers, source_digest, legacy_digest)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [
            translate_view(item, identifiers, source_digest, legacy_digest)
            for item in value
        ]
    if isinstance(value, str):
        return (
            legacy_digest if value == source_digest else identifiers.get(value, value)
        )
    return value
