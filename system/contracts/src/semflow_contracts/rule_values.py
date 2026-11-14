"""Frozen rule and corpus identities shared with scanning and verification."""

from uuid import UUID

from pydantic import Field

from semflow_contracts.common import (
    ArtifactRef,
    Contract,
    Digest,
    Language,
    RulePurpose,
)


class RuleRef(Contract):
    rule_id: UUID
    version: str = Field(min_length=1)
    purpose: RulePurpose
    language: Language
    query: ArtifactRef
    modules: tuple[ArtifactRef, ...] = ()
    dependencies: ArtifactRef
    query_hash: Digest


class CollectionRef(Contract):
    name: str = Field(pattern=r"^(reference|rule_example)$")
    version: str = Field(min_length=1)
    document_ids: tuple[UUID, ...]
    digest: Digest


class EmbeddingIdentity(Contract):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    dimensions: int = Field(ge=1)
    index_digest: Digest


class CorpusSnapshot(Contract):
    snapshot_id: UUID
    manifest: ArtifactRef
    digest: Digest
    collections: tuple[CollectionRef, ...]
    embedding: EmbeddingIdentity | None = None
