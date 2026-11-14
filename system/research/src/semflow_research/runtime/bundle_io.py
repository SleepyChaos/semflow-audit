"""Receive typed scientific bundles, verify bytes, then import frozen inputs."""

from semflow_contracts.bundles import (
    CandidateBundle,
    DecisionBundle,
    EvidenceBundle,
    StaticFindingBundle,
)
from semflow_contracts.common import BundleRef, EntityRef
from semflow_contracts.errors import ResearchError

from semflow_research.runtime.bundle_reader import (
    authorize_records,
    load_bundle,
    resolve_bundle,
)
from semflow_research.state.models import Candidate, Evidence, ExecutionRecord


def import_targets(
    context,
    candidates_ref,
    evidence_ref,
    *,
    decisions_ref=None,
    source_execution_ids=None,
):
    context, candidate_input = resolve_bundle(context, candidates_ref, CandidateBundle)
    candidates = candidate_input.records
    if decisions_ref is not None and not candidates:
        raise ResearchError(
            "invalid_contract", "Downstream target bundle cannot be empty"
        )
    context, evidence_input = resolve_bundle(context, evidence_ref, EvidenceBundle)
    evidences = evidence_input.records
    producers = candidate_input.producers | evidence_input.producers
    # Interface peer: public.discovery_requests.assemble_discovery. AGENT: this
    # set names verified leaf bundle producers, including empty bundles; an
    # index coordinator ID cannot replace them. Update both boundaries together.
    if source_execution_ids is not None and set(source_execution_ids) != producers:
        raise ResearchError(
            "identity_mismatch",
            "Declared review producers differ from verified leaf input bundles",
        )
    context = authorize_records(context, producers)
    known = {record.evidence_id: record for record in evidences}
    for record in evidences:
        if record.kind == "code":
            context.source.validate(record)
        elif record.snapshot_id != context.spec.source.snapshot_id:
            raise ResearchError(
                "evidence_invalid", "Non-code evidence belongs to another snapshot"
            )
    decisions = ()
    if decisions_ref:
        context, decisions = load_bundle(context, decisions_ref, DecisionBundle)
    selected_ids = {record.candidate_id for record in candidates}
    latest = {}
    for decision in sorted(
        decisions, key=lambda row: (row.created_at, str(row.decision_id))
    ):
        if (
            decision.target.bundle
            != candidate_input.membership.get(decision.target.entity_id)
            or decision.target.entity_id not in selected_ids
        ):
            raise ResearchError(
                "identity_mismatch",
                "Decision target is not in the frozen target bundle",
            )
        if (
            decision.actor.kind == "experiment_fixture"
            and context.spec.policy.decision_policy != "experiment_declared"
        ):
            raise ResearchError(
                "invalid_contract",
                "This execution only permits explicit human decisions",
            )
        if any(
            ref.entity_id not in known
            or ref.bundle != evidence_input.membership.get(ref.entity_id)
            or ref.execution_id != known[ref.entity_id].execution_id
            for ref in decision.evidence_refs
        ):
            raise ResearchError(
                "evidence_invalid",
                "Decision cites evidence outside its explicit input bundle",
            )
        latest[decision.target.entity_id] = decision
    for candidate in candidates:
        context.source._slice(
            candidate.primary_location.path,
            candidate.primary_location.start_line,
            candidate.primary_location.end_line,
        )
        if (
            candidate.primary_location.file_sha256
            != context.source.files[candidate.primary_location.path].sha256
        ):
            raise ResearchError(
                "evidence_invalid", "Candidate location has a different file digest"
            )
        for ref in candidate.evidence_refs:
            if (
                ref.entity_id not in known
                or ref.bundle != evidence_input.membership.get(ref.entity_id)
                or known[ref.entity_id].execution_id != ref.execution_id
            ):
                raise ResearchError(
                    "evidence_invalid",
                    "Candidate cites evidence outside its declared evidence bundle",
                )
        if not any(
            record.kind == "code"
            and record.location.path == candidate.primary_location.path
            and record.location.start_line
            <= candidate.primary_location.start_line
            <= record.location.end_line
            for record in (known[ref.entity_id] for ref in candidate.evidence_refs)
        ):
            raise ResearchError(
                "evidence_invalid",
                "Candidate location is not covered by its real source evidence",
            )
        decision = latest.get(candidate.candidate_id)
        if decisions_ref and (decision is None or decision.status != "confirmed"):
            raise ResearchError(
                "invalid_contract",
                "Downstream generation requires an explicit confirmed target decision",
            )
        source_ref = EntityRef(
            execution_id=candidate.execution_id,
            entity_id=candidate.candidate_id,
            bundle=candidate_input.membership[candidate.candidate_id],
        )
        if candidate.origin == "codeql" and candidate.static_finding_ref is None:
            raise ResearchError(
                "invalid_contract",
                "CodeQL input must retain its original static finding identity",
            )
        finding = None
        if candidate.static_finding_ref is not None:
            context, findings = load_bundle(
                context,
                BundleRef(
                    artifact=candidate.static_finding_ref.bundle,
                    entity_ids=(candidate.static_finding_ref.entity_id,),
                ),
                StaticFindingBundle,
            )
            finding = findings[0]
            if finding.locations[0] != candidate.primary_location:
                raise ResearchError(
                    "evidence_invalid",
                    "Static candidate location differs from the original SARIF finding",
                )
        imported = Candidate(
            source_ref=source_ref,
            static_finding_id=finding.raw_id if finding else None,
            id=candidate.candidate_id,
            snapshot_id=context.spec.source.snapshot_id,
            execution_id=candidate.execution_id,
            origin="static" if candidate.origin == "codeql" else "ai",
            title=candidate.title,
            description=candidate.description,
            weakness=candidate.weakness,
            status=decision.status if decision else "pending",
            identity_key=candidate.identity_key,
            location={
                "file": candidate.primary_location.path,
                "line": candidate.primary_location.start_line,
            },
            evidence_ids=[str(ref.entity_id) for ref in candidate.evidence_refs],
        )
        freeze_input(context, imported, candidate.execution_id)
        if finding is not None:
            source = context.source_records.get(context.spec.source.snapshot_id)
            raw = {
                "id": finding.raw_id,
                "rule_version": finding.rule_version,
                "origin": finding.origin,
                "rule": finding.rule,
                "message": finding.message,
                "locations": [
                    {
                        "file": point.path,
                        "line": point.start_line,
                        "end_line": point.end_line,
                        "column": point.start_column or 0,
                    }
                    for point in finding.locations
                ],
                "code_flows": [
                    [
                        {
                            "file": point.path,
                            "line": point.start_line,
                            "column": point.start_column or 0,
                            "end_line": point.end_line,
                        }
                        for point in flow
                    ]
                    for flow in finding.code_flows
                ],
                "tags": list(finding.tags),
                "level": finding.level,
                "security_severity": finding.security_severity,
            }
            context.source_records.update(
                source.id,
                findings=[
                    *{row["id"]: row for row in [*source.findings, raw]}.values()
                ],
                finding_candidate_refs={
                    **source.finding_candidate_refs,
                    finding.raw_id: source_ref,
                },
                finding_refs={
                    **source.finding_refs,
                    finding.raw_id: candidate.static_finding_ref.bundle,
                },
            )
    for record in evidences:
        location = record.location
        freeze_input(
            context,
            Evidence(
                id=record.evidence_id,
                execution_id=record.execution_id,
                snapshot_id=record.snapshot_id,
                kind=record.kind,
                snapshot_hash=context.spec.source.tree_sha256,
                reference={
                    "file": location.path,
                    "start_line": location.start_line,
                    "end_line": location.end_line,
                }
                if location
                else {},
                content=context.artifacts.read(record.content).decode("utf-8"),
                digest=record.digest,
                provenance=record.provenance.model_dump(mode="json"),
            ),
            record.execution_id,
        )
    # The review pool receives the original full hypothesis, including unknown
    # premises. It must never be reconstructed from a model recommendation.
    for producer in {
        record.execution_id for record in candidates if record.origin != "codeql"
    }:
        hypotheses = []
        for record in candidates:
            if record.execution_id == producer and record.origin != "codeql":
                import json

                hypothesis = (
                    json.loads(context.artifacts.read(record.context))
                    if record.context
                    else {
                        "observation": record.description,
                        "missing_premises": [
                            "Original structured hypothesis context was not supplied"
                        ],
                    }
                )
                hypotheses.append(
                    {**hypothesis, "candidate_id": str(record.candidate_id)}
                )
        freeze_input(
            context,
            ExecutionRecord(
                id=producer,
                snapshot_id=context.spec.source.snapshot_id,
                kind="scout",
                method_version="frozen-input/1",
                result={"units": [{"hypotheses": hypotheses}]},
            ),
            producer,
        )
    return context, candidates


def freeze_input(context, record, producer):
    # These internal timestamps record local storage, not an upstream observation.
    # Re-import of identical public bytes must retain the first storage timestamps.
    previous = context.records.get(type(record), record.id)
    if previous is not None:
        updates = {
            field: getattr(previous, field)
            for field in ("created_at", "updated_at")
            if field in type(record).model_fields
        }
        record = record.model_copy(update=updates)
    context.records.import_record(record, producer)
