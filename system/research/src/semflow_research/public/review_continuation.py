"""Select a candidate and verify its reusable first-round review evidence."""

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from semflow_contracts.discovery import AssessmentRecord, CandidateRecord
from semflow_contracts.errors import ResearchError
from semflow_contracts.evidence import EvidenceRecord

from semflow_research.public.discovery_results import read_result
from semflow_research.public.runs import inspect, specification


@dataclass(frozen=True)
class ReviewSeed:
    previous_execution_id: UUID
    candidate: CandidateRecord
    assessment: AssessmentRecord | None
    code_evidence: tuple[EvidenceRecord, ...]


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
    return ReviewSeed(execution_id, candidate, assessment, tuple(code.values()))
