"""Select a candidate and verify its reusable first-round review evidence."""

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID, uuid4

from semflow_contracts.common import BundleRef
from semflow_contracts.discovery import AssessmentRecord, CandidateRecord
from semflow_contracts.errors import ResearchError
from semflow_contracts.evidence import EvidenceRecord
from semflow_contracts.review_handoff import (
    CandidateReviewAttempt,
    ReviewNextAction,
    ReviewSourceWindow,
)
from semflow_contracts.runs import validate_spec

from semflow_research.public.discovery_results import read_result
from semflow_research.public.implementation import code_digest
from semflow_research.public.runs import inspect, specification


@dataclass(frozen=True)
class ReviewSeed:
    previous_execution_id: UUID
    candidate: CandidateRecord
    assessment: AssessmentRecord | None
    code_evidence: tuple[EvidenceRecord, ...]
    evidence_ids: tuple[UUID, ...]
    security_property: str | None
    next_action: ReviewNextAction | None
    observed_windows: tuple[ReviewSourceWindow, ...]
    attempt: CandidateReviewAttempt | None


def capture(execution_id, candidate_id, *, source, root):
    """Return only selected candidate evidence from a matching frozen source.

    Peer: the future review continuation caller must pass the destination
    SourceSnapshot. Source excerpts are validated on import before model use.
    """
    previous = specification(execution_id, root=root)
    if previous.operation != "review":
        raise ResearchError("invalid_contract", "Expected a prior review execution")
    if (previous.source.snapshot_id, previous.source.tree_sha256) != (
        source.snapshot_id,
        source.tree_sha256,
    ):
        raise ResearchError("identity_mismatch", "Review source snapshot changed")

    receipt = inspect(execution_id, root=root)
    if (
        receipt is None
        or receipt.execution_status != "completed"
        or receipt.result is None
    ):
        raise ResearchError("invalid_contract", "Expected a completed prior review")
    view = read_result(execution_id, root=root)
    candidate = next(
        (row for row in view.candidates if row.candidate_id == candidate_id), None
    )
    if candidate is None or candidate.execution_id != execution_id:
        raise ResearchError(
            "identity_mismatch", "Candidate is outside the prior review"
        )
    if candidate.derived_from is None:
        raise ResearchError("invalid_contract", "Candidate has no frozen review target")

    assessments = [
        row for row in view.assessments if row.candidate_ref.entity_id == candidate_id
    ]
    if len(assessments) > 1:
        raise ResearchError("integrity_error", "Ambiguous prior candidate assessment")
    assessment = assessments[0] if assessments else None
    if assessment and assessment.conclusion in {"supported", "excluded"}:
        raise ResearchError("invalid_contract", "Candidate already has a verdict")

    references = candidate.evidence_refs
    if assessment:
        references += assessment.evidence_refs + assessment.counter_evidence_refs
    indexed = {row.evidence_id: row for row in view.evidence}
    code = {}
    for ref in references:
        evidence = indexed.get(ref.entity_id)
        if (
            evidence is None
            or ref.bundle != receipt.result.evidence.artifact
            or ref.execution_id != execution_id
            or evidence.execution_id != execution_id
            or evidence.snapshot_id != source.snapshot_id
        ):
            raise ResearchError("evidence_invalid", "Prior evidence identity mismatch")
        if evidence.kind == "code":
            body = view.content[evidence.evidence_id]
            if sha256(body.encode()).hexdigest() != evidence.digest:
                raise ResearchError("integrity_error", "Prior evidence digest mismatch")
            code[evidence.evidence_id] = evidence
    handoff = next(
        (
            row
            for row in (
                view.trace.state.get("candidate_handoffs", []) if view.trace else []
            )
            if row["candidate_id"] == str(candidate_id)
        ),
        {},
    )
    attempt = (
        next(
            (
                record
                for record in view.review_report.records
                if record.candidate_ref.entity_id == candidate_id
            ),
            None,
        )
        if view.review_report is not None
        else None
    )
    return ReviewSeed(
        execution_id,
        candidate,
        assessment,
        tuple(code.values()),
        tuple(dict.fromkeys(ref.entity_id for ref in references)),
        handoff.get("security_property"),
        ReviewNextAction.model_validate(handoff["next_action"])
        if "next_action" in handoff
        else None,
        tuple(
            ReviewSourceWindow.model_validate(row)
            for row in handoff.get("observed_source_windows", ())
        ),
        attempt,
    )


def require_continuable(seed):
    if not seed.code_evidence:
        raise ResearchError(
            "evidence_invalid", "Selected candidate has no source evidence"
        )
    if seed.next_action is not None and seed.next_action.kind not in {
        "gather_source",
        "retry_execution",
    }:
        raise ResearchError(
            "invalid_contract",
            "当前候选需要补充材料或人工定位证据，已有快照没有可执行的补证目标。",
        )


def validate_continuation(execution_id, candidate_id, *, root):
    previous = specification(execution_id, root=root)
    seed = capture(execution_id, candidate_id, source=previous.source, root=root)
    require_continuable(seed)
    return seed


def assemble(
    execution_id,
    candidate_id,
    *,
    root,
    execution_id_override=None,
    reuse_cache=True,
    dependency_lock_digest=None,
):
    """Freeze a new review of one unresolved candidate from a published review.

    The receiver in runtime.discovery_operations binds retry_of to the exact
    selected prior producer and verifies the selected evidence again.
    """
    previous = specification(execution_id, root=root)
    seed = capture(execution_id, candidate_id, source=previous.source, root=root)
    require_continuable(seed)
    result = inspect(execution_id, root=root).result
    value = previous.model_dump(mode="json")
    value["execution_id"] = str(execution_id_override or uuid4())
    value["lineage"] = {"retry_of": str(execution_id)}
    value["implementation"]["code_digest"] = code_digest()
    if dependency_lock_digest is not None:
        value["implementation"]["dependency_lock_digest"] = dependency_lock_digest
    value["inputs"]["targets"] = BundleRef(
        artifact=result.candidates.artifact, entity_ids=(candidate_id,)
    ).model_dump(mode="json")
    value["inputs"]["evidence"] = BundleRef(
        artifact=result.evidence.artifact, entity_ids=seed.evidence_ids
    ).model_dump(mode="json")
    value["inputs"]["source_execution_ids"] = [str(execution_id)]
    value["inputs"]["policy"].update(
        version="1" if reuse_cache else "1-no-cache", batch_size=1, max_batches=1
    )
    return validate_spec(value)


def history(execution_id, candidate_id, *, root):
    """Newest first, following explicit continuation lineage only."""
    records, visited = [], set()
    while execution_id not in visited:
        visited.add(execution_id)
        view = read_result(execution_id, root=root)
        report = view.review_report
        if report is None:
            break
        attempt = next(
            (
                row
                for row in report.records
                if row.candidate_ref.entity_id == candidate_id
            ),
            None,
        )
        if attempt is None:
            raise ResearchError(
                "identity_mismatch", "Review history candidate was not found"
            )
        records.append(attempt)
        prior = specification(execution_id, root=root).lineage.retry_of
        if prior is None:
            break
        parent = attempt.previous_candidate_ref
        if parent is None or parent.execution_id != prior:
            raise ResearchError(
                "identity_mismatch", "Review continuation history changed owner"
            )
        execution_id, candidate_id = prior, parent.entity_id
    else:
        raise ResearchError("integrity_error", "Review continuation history is cyclic")
    return tuple(records)
