"""Platform ownership and scope selection -> immutable review input bundles."""

from pathlib import PurePosixPath
from uuid import UUID, uuid4, uuid5

from semflow_contracts.bundles import (
    CandidateBundle,
    EvidenceBundle,
    StaticFindingBundle,
    StaticFindingRecord,
)
from semflow_contracts.common import (
    BundleRef,
    EntityRef,
    SourceLocation,
    canonical_bytes,
)
from semflow_contracts.discovery import CandidateRecord
from semflow_research.public.artifacts import commit
from semflow_research.public.baselines import capture
from semflow_research.public.evidence import read
from sqlmodel import select

from app.adapters.artifacts import ArtifactStore
from app.domain.audit import AuditError
from app.persistence.stage_models import Candidate, StageRun
from app.research_bridge.requests import research_root


def freeze_targets(session, binding, stage, audit, snapshot):
    inputs = stage.inputs
    producer = uuid5(binding.execution_id, "frozen-review-inputs/1")
    directory = ArtifactStore().directory(str(audit.id))
    from semflow_research.public.runs import inspect

    from app.research_bridge.models import ResearchAuditBinding

    scan_binding = session.exec(
        select(ResearchAuditBinding).where(ResearchAuditBinding.audit_id == audit.id)
    ).first()
    receipt = (
        inspect(scan_binding.execution_id, root=research_root())
        if scan_binding and scan_binding.request
        else None
    )
    baseline = receipt.result.baseline if receipt and receipt.result else None
    if baseline is None:
        if not audit.codeql_version:
            raise AuditError("复核需要真实静态基线的工具版本", code="invalid_input")
        baseline = capture(
            snapshot=snapshot,
            source_root=ArtifactStore().source(str(audit.source_run_id)),
            directory=directory,
            root=research_root(),
            execution_id=producer,
            codeql_version=audit.codeql_version,
            query_pack=audit.query_pack,
            suite=audit.suite,
        )
    if (
        baseline.snapshot_id != snapshot.snapshot_id
        or baseline.source_digest != snapshot.tree_sha256
    ):
        raise AuditError("复核静态基线与冻结源码身份不一致", code="integrity_error")
    arguments = {"root": research_root(), "execution_id": producer}
    records, evidences, findings = [], [], []

    def evidence(point):
        row = read(
            snapshot,
            root=research_root(),
            source_root=ArtifactStore().source(str(audit.source_run_id)),
            execution_id=producer,
            path=point["file"],
            start_line=max(1, point["line"] - 8),
            end_line=point["line"] + 12,
        )
        evidences.append(row)
        return row

    def location(point, ev=None):
        ev = ev or evidence(point)
        return SourceLocation(
            snapshot_id=snapshot.snapshot_id,
            path=point["file"],
            start_line=point["line"],
            end_line=point.get("end_line", point["line"]),
            file_sha256=ev.location.file_sha256,
            start_column=point.get("column") or None,
            end_column=point.get("end_column") or None,
        )

    static = audit.findings
    requested = set(inputs["finding_ids"])
    if not requested.issubset({row["id"] for row in static}):
        raise AuditError("复核告警不属于当前审计", code="identity_error")
    if requested:
        static = [row for row in static if row["id"] in requested]
    for row in static:
        point = row["locations"][0]
        if not in_scope(point["file"], inputs["paths"]):
            if requested:
                raise AuditError("指定告警超出已选择范围")
            continue
        ev = evidence(point)
        loc = location(point, ev)
        findings.append(
            StaticFindingRecord(
                finding_id=uuid5(snapshot.snapshot_id, row["id"]),
                execution_id=producer,
                raw_id=row["id"],
                rule_version=row.get("rule_version"),
                origin=row.get("origin", "baseline"),
                rule=row["rule"],
                message=row["message"],
                locations=tuple(
                    location(point, ev if index == 0 else None)
                    for index, point in enumerate(row["locations"])
                ),
                code_flows=tuple(
                    tuple(location(point) for point in flow)
                    for flow in row.get("code_flows", [])
                ),
                tags=tuple(row.get("tags", [])),
                level=row.get("level", "warning"),
                security_severity=str(row["security_severity"])
                if row.get("security_severity") is not None
                else None,
                sarif=baseline.sarif,
            )
        )
        records.append((row, loc, ev))
    finding_ref = commit(
        canonical_bytes(
            StaticFindingBundle(
                execution_id=producer,
                snapshot_id=snapshot.snapshot_id,
                records=tuple(findings),
            )
        ),
        kind="materials",
        schema_version="semflow.research.bundle/1",
        **arguments,
    )
    scouts = (
        session.exec(
            select(Candidate)
            .join(StageRun, Candidate.stage_id == StageRun.id)
            .where(Candidate.audit_id == audit.id, StageRun.kind == "scout")
            .order_by(Candidate.created_at)
        ).all()
        if inputs["include_scout"]
        else []
    )
    selected = set(map(UUID, inputs["scout_candidate_ids"]))
    if not selected.issubset({row.id for row in scouts}):
        raise AuditError("粗筛候选不属于当前审计或未开启粗筛输入")
    scouts = list(
        {
            row.identity_key: row
            for row in scouts
            if not selected or row.id in selected
        }.values()
    )
    scout_rows = []
    for row in scouts:
        if not in_scope(row.location["file"], inputs["paths"]):
            if selected:
                raise AuditError("指定粗筛目标超出范围")
            continue
        ev = evidence(row.location)
        original = session.get(StageRun, row.stage_id)
        hypothesis = next(
            (
                h
                for unit in original.result.get("units", [])
                for h in unit.get("hypotheses", [])
                if h["candidate_id"] == str(row.id)
            ),
            None,
        )
        scout_rows.append((row, ev, hypothesis))
    # WIRE-SEND:research.bundle — peer: runtime.bundle_io.import_targets.
    # AGENT: these are input projections with a new producer, actual excerpts
    # and preserved hypothesis premises, never automatic human confirmation.
    evidence_ref = commit(
        canonical_bytes(
            EvidenceBundle(
                execution_id=producer,
                snapshot_id=snapshot.snapshot_id,
                records=tuple(evidences),
            )
        ),
        kind="evidence_bundle",
        schema_version="semflow.research.bundle/1",
        **arguments,
    )
    candidates = []
    for raw, loc, ev in records:
        candidates.append(
            CandidateRecord(
                candidate_id=uuid4(),
                execution_id=producer,
                origin="codeql",
                title=raw["rule"],
                description="CodeQL observation: " + raw["message"],
                weakness="unknown",
                primary_location=loc,
                identity_key="static:" + raw["id"],
                novelty="known_location",
                evidence_refs=(
                    EntityRef(
                        execution_id=producer,
                        entity_id=ev.evidence_id,
                        bundle=evidence_ref,
                    ),
                ),
                static_finding_ref=EntityRef(
                    execution_id=producer,
                    entity_id=uuid5(snapshot.snapshot_id, raw["id"]),
                    bundle=finding_ref,
                ),
            )
        )
    for row, ev, hypothesis in scout_rows:
        identifier = uuid4()
        context = (
            commit(
                canonical_bytes(
                    {
                        **hypothesis,
                        "candidate_id": str(identifier),
                        "evidence_ids": [str(ev.evidence_id)],
                    }
                ),
                kind="materials",
                schema_version="semflow.hypothesis/1",
                **arguments,
            )
            if hypothesis
            else None
        )
        candidates.append(
            CandidateRecord(
                candidate_id=identifier,
                execution_id=producer,
                origin="scout",
                title=row.title,
                description=row.description,
                weakness=row.weakness,
                primary_location=SourceLocation(
                    snapshot_id=snapshot.snapshot_id,
                    path=row.location["file"],
                    start_line=row.location["line"],
                    end_line=row.location.get("end_line", row.location["line"]),
                    file_sha256=ev.location.file_sha256,
                ),
                identity_key=row.identity_key,
                novelty="unknown",
                evidence_refs=(
                    EntityRef(
                        execution_id=producer,
                        entity_id=ev.evidence_id,
                        bundle=evidence_ref,
                    ),
                ),
                context=context,
            )
        )
        binding.entity_map = {
            **binding.entity_map,
            f"{producer}/{identifier}": str(row.id),
        }
    candidate_ref = commit(
        canonical_bytes(
            CandidateBundle(
                execution_id=producer,
                snapshot_id=snapshot.snapshot_id,
                records=tuple(candidates),
            )
        ),
        kind="candidate_bundle",
        schema_version="semflow.research.bundle/1",
        **arguments,
    )
    return {
        "targets": BundleRef(artifact=candidate_ref).model_dump(mode="json"),
        "evidence": BundleRef(artifact=evidence_ref).model_dump(mode="json"),
        "source_execution_ids": [str(producer)],
        "baseline": baseline.model_dump(mode="json"),
        "policy": {
            "version": (
                ("4" if inputs.get("strict_refutations") else "3")
                if stage.prompt_version == "12"
                else "1"
            ),
            "scheduler": "clustered_v2",
            "scope_paths": inputs["paths"],
            "max_steps": inputs["max_steps"],
            "max_context_chars": inputs["max_context_chars"],
            "batch_size": inputs["batch_size"],
            "max_batches": inputs["max_batches"],
            "supplement_insufficient": inputs["supplement_insufficient"],
        },
    }


def in_scope(path, scopes):
    return not scopes or any(
        PurePosixPath(path).is_relative_to(PurePosixPath(scope)) for scope in scopes
    )
