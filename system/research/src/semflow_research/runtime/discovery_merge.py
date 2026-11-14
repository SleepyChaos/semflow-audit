"""Index immutable discovery outputs; preserve producer IDs and review lineage."""

from semflow_contracts.bundles import BundleIndex, CandidateBundle
from semflow_contracts.common import BundleRef, EntityRef, canonical_bytes
from semflow_contracts.discovery import CoverageReport
from semflow_contracts.results import DiscoveryResult

from semflow_research.runtime.bundle_reader import authorize_artifacts, resolve_bundle
from semflow_research.runtime.discovery_outputs import commit_json
from semflow_research.runtime.ledger import input_artifacts

KINDS = {
    "candidate": "candidate_bundle",
    "evidence": "evidence_bundle",
    "assessment": "materials",
}


def index(context, entity_type, members):
    # WIRE-SEND:research.bundle_index — peer: bundle_reader.resolve_bundle.
    # AGENT: retain leaf producer/record IDs, immutable byte references and subset
    # selection. The coordinator owns only the index, never the member evidence.
    body = BundleIndex(
        execution_id=context.execution_id,
        snapshot_id=context.spec.source.snapshot_id,
        entity_type=entity_type,
        members=tuple(members),
    )
    ref = context.artifacts.commit(
        canonical_bytes(body),
        kind=KINDS[entity_type],
        schema_version=body.schema_version,
    )
    return BundleRef(artifact=ref)


def source_indexes(context, results):
    """Review sees only explicit outputs after independent branches finish."""
    candidates = index(
        context,
        "candidate",
        [result.result.candidates for result in results if result.result],
    )
    evidence = index(
        context,
        "evidence",
        [result.result.evidence for result in results if result.result],
    )
    context = authorize_artifacts(
        context, tuple(ref for result in results for ref in input_artifacts(result))
    )
    return context, candidates, evidence


def merge(
    context,
    outcomes,
    branches,
    *,
    source_candidates,
    source_evidence,
    review_result=None,
):
    context = authorize_artifacts(
        context, tuple(ref for result in outcomes for ref in input_artifacts(result))
    )
    context, original = resolve_bundle(context, source_candidates, CandidateBundle)
    original_refs = {
        row.candidate_id: EntityRef(
            execution_id=row.execution_id,
            entity_id=row.candidate_id,
            bundle=original.membership[row.candidate_id],
        )
        for row in original.records
    }
    evidence_members = [source_evidence]
    candidate_members = [source_candidates]
    assessments = None
    reviewed, unreviewed = [], list(original_refs.values())
    root_relations = None
    if review_result and review_result.result:
        output = review_result.result
        context, revised = resolve_bundle(context, output.candidates, CandidateBundle)
        represented = {
            row.derived_from for row in revised.records if row.derived_from is not None
        }
        remaining = {
            identifier: ref
            for identifier, ref in original_refs.items()
            if ref not in represented
        }
        candidate_members = [
            output.candidates,
            BundleRef(
                artifact=source_candidates.artifact,
                entity_ids=tuple(sorted(remaining, key=str)),
            ),
        ]
        evidence_members.append(output.evidence)
        assessments = output.assessments
        reviewed = list(output.coverage.reviewed_candidate_refs)
        unreviewed = [*output.coverage.unreviewed_candidate_refs, *remaining.values()]
        root_relations = output.root_relations
    partial_reasons = []
    for branch in branches:
        result = next(
            (
                result
                for result in outcomes
                if result.execution_id == branch.execution_id
            ),
            None,
        )
        if branch.status != "completed":
            partial_reasons.append(
                branch.branch
                + ": "
                + (branch.failure.message if branch.failure else branch.status)
            )
        if result and result.completeness.status != "full":
            partial_reasons.extend(
                branch.branch + ": " + reason
                for reason in result.completeness.reasons
                or ("Incomplete source or candidate coverage",)
            )
    if unreviewed:
        partial_reasons.append(
            "Candidates remain unreviewed; source hypotheses are not confirmations"
        )
    # When review was not requested, raw candidates are deliberately unassessed.
    # Source scanning can still be complete; assessment coverage stays explicit.
    status = "full"
    if partial_reasons:
        status = (
            "partial"
            if any(result.result is not None for result in outcomes)
            else "none"
        )
    coverage = CoverageReport(
        status=status,
        scope_manifest=commit_json(
            context,
            {"branches": [branch.model_dump(mode="json") for branch in branches]},
            "coverage",
        ),
        inspected_units=commit_json(
            context,
            {
                "branch_coverages": [
                    result.result.coverage.model_dump(mode="json")
                    for result in outcomes
                    if result.result
                ]
            },
            "coverage",
        ),
        missing_units=commit_json(
            context,
            {
                "reasons": partial_reasons,
                "unreviewed": [ref.model_dump(mode="json") for ref in unreviewed],
            },
            "coverage",
        ),
        reasons=tuple(dict.fromkeys(partial_reasons)),
        reviewed_candidate_refs=tuple(reviewed),
        unreviewed_candidate_refs=tuple(unreviewed),
    )
    scan = next(
        (
            result.result
            for result in outcomes
            if result.operation == "scan" and result.result
        ),
        None,
    )
    return DiscoveryResult(
        baseline=scan.baseline if scan else None,
        candidates=index(context, "candidate", candidate_members),
        evidence=index(context, "evidence", evidence_members),
        assessments=assessments,
        static_findings=scan.static_findings if scan else None,
        coverage=coverage,
        branches=tuple(branches),
        root_relations=root_relations,
    )
