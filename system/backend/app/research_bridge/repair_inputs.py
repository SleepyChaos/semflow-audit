"""Freeze platform authorization and exact cited source into repair input bundles."""

import hashlib
from datetime import UTC
from uuid import UUID, uuid5

from semflow_contracts.bundles import CandidateBundle, DecisionBundle, EvidenceBundle
from semflow_contracts.common import EntityRef, SourceLocation, canonical_bytes
from semflow_contracts.discovery import CandidateRecord
from semflow_contracts.evidence import ActorRef, DecisionRecord
from semflow_research.public.artifacts import commit
from semflow_research.public.evidence import read
from sqlmodel import select

from app.domain.audit import AuditError
from app.persistence.stage_models import Candidate, Decision, Evidence, StageRun
from app.research_bridge.requests import research_root


def freeze_targets(
    binding, stage, audit, session, snapshot, source_root, *, static_refs=None
):
    requested = tuple(map(UUID, stage.inputs["candidate_ids"]))
    candidates = session.exec(
        select(Candidate).where(
            Candidate.audit_id == audit.id, Candidate.id.in_(requested)
        )
    ).all()
    by_id = {row.id: row for row in candidates}
    if (
        not requested
        or len(set(requested)) != len(requested)
        or set(by_id) != set(requested)
    ):
        raise AuditError("修复目标不存在或不属于本次审计", code="target_not_authorized")
    candidates = [by_id[identifier] for identifier in requested]
    decisions = {}
    for decision in session.exec(
        select(Decision)
        .where(Decision.candidate_id.in_(requested))
        .order_by(Decision.created_at, Decision.id)
    ).all():
        decisions[decision.candidate_id] = decision
    producer = uuid5(binding.execution_id, "repair-inputs/1")
    arguments = {"root": research_root(), "execution_id": producer}
    frozen, evidence_rows, mapping = [], {}, dict(binding.entity_map)
    for row in candidates:
        decision = decisions.get(row.id)
        if (
            row.status != "confirmed"
            or decision is None
            or decision.status != "confirmed"
        ):
            raise AuditError(
                "修复只接受最新人工明确确认的候选", code="target_not_authorized"
            )
        if not decision.evidence_ids or not set(decision.evidence_ids).issubset(
            row.evidence_ids
        ):
            raise AuditError(
                "确认决策没有关联当前候选证据", code="target_not_authorized"
            )
        for identifier in dict.fromkeys([*row.evidence_ids, *decision.evidence_ids]):
            identifier = UUID(identifier)
            ev = session.get(Evidence, identifier)
            origin = session.get(StageRun, ev.stage_id) if ev else None
            if (
                ev is None
                or origin is None
                or ev.audit_id != audit.id
                or origin.audit_id != audit.id
                or ev.snapshot_hash != audit.snapshot_hash
                or hashlib.sha256(ev.content.encode()).hexdigest() != ev.digest
            ):
                raise AuditError("确认引用的证据身份或内容失效", code="integrity_error")
            if ev.kind != "code":
                raise AuditError(
                    "当前修复桥接仅支持可逐字核验的源码确认依据",
                    code="unsupported_operation",
                )
            point = ev.reference
            captured = read(
                snapshot,
                root=research_root(),
                source_root=source_root,
                execution_id=producer,
                path=point["file"],
                start_line=point["start_line"],
                end_line=point["end_line"],
            )
            # WIRE-SEND:research.evidence — peer: bundle_io.import_targets / SnapshotReader.validate.
            # AGENT: this converts the legacy excerpt digest to a typed source proof;
            # rereading different evidence must never silently renew a human decision.
            if (
                captured.digest != ev.digest
                or captured.location.end_line != point["end_line"]
            ):
                raise AuditError("确认依据与冻结源码不一致", code="integrity_error")
            evidence_rows[identifier] = captured
        primary = next(
            (
                evidence_rows[UUID(i)]
                for i in row.evidence_ids
                if evidence_rows[UUID(i)].location.path == row.location["file"]
                and evidence_rows[UUID(i)].location.start_line <= row.location["line"]
                and evidence_rows[UUID(i)].location.end_line
                >= row.location.get("end_line", row.location["line"])
            ),
            None,
        )
        if primary is None:
            raise AuditError("候选位置没有实际源码证据支持", code="integrity_error")
        if (
            row.static_finding_id
            and static_refs is not None
            and row.static_finding_id not in static_refs
        ):
            raise AuditError("修复目标静态告警不在冻结基线中", code="identity_mismatch")
        if (
            row.static_finding_id
            and static_refs
            and row.static_finding_id in static_refs
        ):
            loc = static_refs[row.static_finding_id][1]
            if (loc.path, loc.start_line) != (
                row.location["file"],
                row.location["line"],
            ):
                raise AuditError("修复候选位置与静态告警不同", code="integrity_error")
        identifier = uuid5(producer, "candidate/" + str(row.id))
        mapping[f"{producer}/{identifier}"] = str(row.id)
        frozen.append((row, decision, identifier, primary))
    evidence_ref = commit(
        canonical_bytes(
            EvidenceBundle(
                execution_id=producer,
                snapshot_id=snapshot.snapshot_id,
                records=tuple(
                    {ev.evidence_id: ev for ev in evidence_rows.values()}.values()
                ),
            )
        ),
        kind="evidence_bundle",
        schema_version="semflow.research.bundle/1",
        **arguments,
    )

    def refs(ids):
        return tuple(
            EntityRef(
                execution_id=producer,
                entity_id=evidence_rows[UUID(i)].evidence_id,
                bundle=evidence_ref,
            )
            for i in dict.fromkeys(ids)
        )

    static_refs = static_refs or {}
    records = tuple(
        CandidateRecord(
            candidate_id=identifier,
            execution_id=producer,
            origin="review",
            title=row.title,
            description=row.description,
            weakness=row.weakness if row.weakness.startswith("CWE-") else "unknown",
            static_finding_ref=static_refs[row.static_finding_id][0]
            if row.static_finding_id in static_refs
            else None,
            primary_location=static_refs[row.static_finding_id][1]
            if row.static_finding_id in static_refs
            else SourceLocation(
                snapshot_id=snapshot.snapshot_id,
                path=row.location["file"],
                start_line=row.location["line"],
                end_line=row.location.get("end_line", row.location["line"]),
                file_sha256=primary.location.file_sha256,
            ),
            identity_key=row.identity_key,
            novelty="known_location",
            evidence_refs=refs(row.evidence_ids),
        )
        for row, _, identifier, primary in frozen
    )
    candidate_ref = commit(
        canonical_bytes(
            CandidateBundle(
                execution_id=producer, snapshot_id=snapshot.snapshot_id, records=records
            )
        ),
        kind="candidate_bundle",
        schema_version="semflow.research.bundle/1",
        **arguments,
    )
    # WIRE-SEND:research.bundle — peer: runtime.bundle_io.import_targets.
    # AGENT: platform IDs remain in entity_map; scientific producers and decisions
    # have independent identities. Preserve the exact latest decision and evidence.
    decision_ref = commit(
        canonical_bytes(
            DecisionBundle(
                execution_id=producer,
                snapshot_id=snapshot.snapshot_id,
                records=tuple(
                    DecisionRecord(
                        decision_id=uuid5(producer, "decision/" + str(decision.id)),
                        target=EntityRef(
                            execution_id=producer,
                            entity_id=identifier,
                            bundle=candidate_ref,
                        ),
                        snapshot_id=snapshot.snapshot_id,
                        status=decision.status,
                        actor=ActorRef(kind="human", id=str(decision.actor_id)),
                        reason=decision.reason,
                        evidence_refs=refs(decision.evidence_ids),
                        created_at=decision.created_at.replace(tzinfo=UTC)
                        if decision.created_at.tzinfo is None
                        else decision.created_at,
                    )
                    for _, decision, identifier, _ in frozen
                ),
            )
        ),
        kind="decision_bundle",
        schema_version="semflow.research.bundle/1",
        **arguments,
    )
    binding.entity_map = mapping
    return {
        "snapshot_id": str(snapshot.snapshot_id),
        "candidates": {"artifact": candidate_ref.model_dump(mode="json")},
        "evidence": {"artifact": evidence_ref.model_dump(mode="json")},
        "decisions": {"artifact": decision_ref.model_dump(mode="json")},
    }, candidates


def platform_targets(binding, result, requested):
    """Decode only deterministic mappings made by freeze_targets, never arbitrary IDs."""
    producer = uuid5(binding.execution_id, "repair-inputs/1")
    targets = []
    # Peer: freeze_targets candidate UUID creation above / RepairResult.target_refs.
    # AGENT: changing either ID formula requires changing this receiver and its
    # integrity checks; set equality alone would allow targets to be swapped.
    for ref in result.target_refs:
        mapped = binding.entity_map.get(f"{ref.execution_id}/{ref.entity_id}")
        if (
            mapped is None
            or ref.execution_id != producer
            or mapped not in requested
            or uuid5(producer, "candidate/" + mapped) != ref.entity_id
        ):
            raise AuditError("修复目标缺少可信的平台输入映射", code="identity_mismatch")
        targets.append(mapped)
    if len(set(targets)) != len(targets) or set(targets) != set(requested):
        raise AuditError("修复目标集合变化", code="identity_mismatch")
    return targets
