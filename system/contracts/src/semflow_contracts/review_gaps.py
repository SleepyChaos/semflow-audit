"""Model requests and verified evidence-gap diagnostics for navigated review."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from semflow_contracts.common import Contract

GapType = Literal["repository", "runtime", "external", "unresolved"]
GapAction = Literal["find_symbol", "find_references", "read_source", "request_material"]


class EvidenceGapRequest(Contract):
    gap_type: GapType
    description: str = Field(min_length=1, max_length=500)
    target_symbol: str | None = Field(default=None, max_length=180)
    target_path: str | None = Field(default=None, max_length=300)
    required_fact: str | None = Field(default=None, max_length=300)
    suggested_action: GapAction | None = None
    priority: Literal["high", "normal"] = "normal"


class ReviewEvidenceGap(EvidenceGapRequest):
    # Peer: research.discovery.review_gap_planner and CandidateReviewAttempt.
    gap_id: str = Field(min_length=1)
    candidate_id: UUID
    status: Literal[
        "pending", "searching", "found", "not_found", "blocked", "exhausted"
    ]
    attempt_count: int = Field(default=0, ge=0)
    evidence_refs: tuple[UUID, ...] = ()
    failure_reason: str | None = None
