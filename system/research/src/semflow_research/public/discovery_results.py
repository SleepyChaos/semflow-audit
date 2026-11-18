"""Read a published discovery result through typed, verified public codecs."""

from dataclasses import dataclass

from semflow_contracts.bundles import (
    AssessmentBundle,
    CandidateBundle,
    EvidenceBundle,
    StaticFindingBundle,
)
from semflow_contracts.common import BundleRef
from semflow_contracts.discovery_trace import DiscoveryTrace
from semflow_contracts.errors import ResearchError
from semflow_contracts.review_handoff import CandidateReviewReport

from semflow_research.runtime.bundle_reader import read_bundle
from semflow_research.runtime.ledger import LocalLedger


@dataclass(frozen=True)
class DiscoveryView:
    candidates: tuple
    evidence: tuple
    assessments: tuple
    findings: tuple
    trace: DiscoveryTrace | None
    content: dict
    project_map: dict | None
    review_report: CandidateReviewReport | None = None


def read_result(execution_id, *, root):
    ledger = LocalLedger(root)
    result = ledger.inspect(execution_id)
    if result is None or result.module != "discovery" or result.result is None:
        raise ResearchError("invalid_contract", "No published discovery payload")
    with ledger._connect() as db:
        row = ledger._row(db, execution_id)
        store = ledger._store(row)
        import json

        from semflow_contracts.runs import validate_spec

        spec = validate_spec(json.loads(row["spec"]))
    payload = result.result
    values, memberships = {}, {}
    for name, reference, schema in (
        ("candidates", payload.candidates, CandidateBundle),
        ("evidence", payload.evidence, EvidenceBundle),
        ("assessments", payload.assessments, AssessmentBundle),
        ("findings", payload.static_findings, StaticFindingBundle),
    ):
        if reference is not None:
            store, loaded = read_bundle(
                store, spec.source.snapshot_id, reference, schema
            )
            values[name] = loaded.records
            memberships[name] = loaded.membership
        else:
            values[name] = ()
    trace = None
    for candidate in values["candidates"]:
        if candidate.static_finding_ref is not None:
            static = candidate.static_finding_ref
            store, loaded = read_bundle(
                store,
                spec.source.snapshot_id,
                BundleRef(artifact=static.bundle, entity_ids=(static.entity_id,)),
                StaticFindingBundle,
            )
            values["findings"] = tuple(
                {
                    row.finding_id: row
                    for row in (*values["findings"], *loaded.records)
                }.values()
            )
    if payload.analysis_trace is not None:
        # WIRE-RECV:research.result — peer: runtime.discovery_outputs.export.
        # AGENT: trace is diagnostics only. Projection uses typed entities for
        # conclusions and must explicitly map identities, source digests and status.
        trace = DiscoveryTrace.model_validate_json(store.read(payload.analysis_trace))
        if (
            trace.execution_id,
            trace.snapshot_id,
            trace.source_digest,
            trace.method_version,
        ) != (
            execution_id,
            spec.source.snapshot_id,
            spec.source.tree_sha256,
            spec.implementation.method_version,
        ):
            raise ResearchError(
                "identity_mismatch",
                "Discovery trace belongs to another method or source",
            )
    report = read_review_report(result, spec, store, values, memberships)
    return DiscoveryView(
        review_report=report,
        **values,
        trace=trace,
        project_map=json.loads(store.read(payload.project_map))
        if payload.project_map
        else None,
        content={
            row.evidence_id: store.read(row.content).decode("utf-8")
            for row in values["evidence"]
        },
    )


def read_review_report(result, spec, store, values, memberships):
    ref = result.result.candidate_reviews
    if ref is None:
        return None
    owner = (
        result.execution_id
        if result.operation == "review"
        else next(
            (
                branch.execution_id
                for branch in result.result.branches
                if branch.branch == "review"
            ),
            None,
        )
    )
    if (
        ref.owner_execution_id != owner
        or ref.schema_version != "semflow.candidate-review-report/1"
    ):
        raise ResearchError(
            "identity_mismatch", "Unexpected candidate-review report producer"
        )
    report = CandidateReviewReport.model_validate_json(store.read(ref))
    if (report.execution_id, report.snapshot_id, report.source_digest) != (
        owner,
        spec.source.snapshot_id,
        spec.source.tree_sha256,
    ):
        raise ResearchError(
            "identity_mismatch", "Review report belongs to another source"
        )
    candidates = {row.candidate_id: row for row in values["candidates"]}
    evidence = {row.evidence_id: row for row in values["evidence"]}
    assessments = {row.candidate_ref.entity_id: row for row in values["assessments"]}
    for row in report.records:
        candidate_id = row.candidate_ref.entity_id
        candidate = candidates.get(candidate_id)
        if (
            candidate is None
            or candidate.execution_id != owner
            or row.location != candidate.primary_location
            or row.previous_candidate_ref != candidate.derived_from
            or row.candidate_ref.bundle != memberships["candidates"].get(candidate_id)
            or row.assessment != assessments.get(candidate_id)
        ):
            raise ResearchError(
                "identity_mismatch", "Candidate review row does not match its bundles"
            )
        for fact in row.premises:
            for citation in fact.evidence_refs:
                record = evidence.get(citation.entity_id)
                if (
                    record is None
                    or citation.execution_id != record.execution_id
                    or citation.bundle
                    != memberships["evidence"].get(citation.entity_id)
                ):
                    raise ResearchError(
                        "evidence_invalid",
                        "Review premise cites another evidence bundle",
                    )
    return report
