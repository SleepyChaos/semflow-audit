"""Frozen, opt-in security-specific guidance for source-only Scout."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import Field

from semflow_contracts.common import Contract
from semflow_contracts.rule_values import CorpusSnapshot


class SecuritySpecificationHint(Contract):
    specification_id: UUID
    statement: str = Field(min_length=30, max_length=600)


class SecuritySpecificationPolicy(Contract):
    # Peers: public.discovery_requests, platform Scout request, and
    # discovery.specification_guidance. A missing policy preserves ordinary Scout.
    corpus: CorpusSnapshot
    as_of: date
    excluded_repositories: tuple[str, ...] = Field(default=(), max_length=100)
    top_k: int = Field(default=3, ge=1, le=5)
    min_shared_terms: int = Field(default=2, ge=1, le=8)
    timeout_seconds: float = Field(default=3.0, gt=0, le=20)
    retrieval_mode: Literal["bm25"] = "bm25"
