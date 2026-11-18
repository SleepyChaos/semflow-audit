"""Candidate-scoped review evidence reuse receipts."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from semflow_contracts.common import Contract, Digest, SourceLocation


class ReviewMemoryIdentity(Contract):
    # Full snapshot covers dependencies outside the cited files. Subject binds
    # task, candidate, and property; there is no cross-candidate fact sharing.
    snapshot_id: UUID
    source_digest: Digest
    subject_digest: Digest
    analysis_digest: Digest
    validation_version: Literal["semflow.review-source-gate/1"] = (
        "semflow.review-source-gate/1"
    )


class ReviewCachedSource(Contract):
    previous_evidence_id: UUID
    evidence_id: UUID
    location: SourceLocation
    content_digest: Digest
    disposition: Literal["reused", "reread"]


class ReviewCacheReceipt(Contract):
    # Peers: review_continuation.attach writes; public discovery_results reads.
    schema_version: Literal["semflow.review-cache-receipt/1"] = (
        "semflow.review-cache-receipt/1"
    )
    mode: Literal["reuse", "reread"]
    previous: ReviewMemoryIdentity
    current: ReviewMemoryIdentity
    source: tuple[ReviewCachedSource, ...]
    source_hits: int = Field(ge=0)
    source_misses: int = Field(ge=0)
    fact_hits: int = Field(ge=0)
    fact_misses: int = Field(ge=0)
    invalidation_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def counts_and_identity(self):
        hits = sum(row.disposition == "reused" for row in self.source)
        if (self.source_hits, self.source_misses) != (hits, len(self.source) - hits):
            raise ValueError("Cache counts do not match restored source records")
        if len({row.evidence_id for row in self.source}) != len(self.source):
            raise ValueError("Duplicate restored evidence")
        if any(
            row.location.snapshot_id != self.current.snapshot_id for row in self.source
        ):
            raise ValueError("Cache source records have a different snapshot")
        if self.fact_hits and (self.previous != self.current or self.mode != "reuse"):
            raise ValueError("Facts cannot be reused for another analysis")
        return self
