"""Frozen corpus content and provenance, independent of platform visibility tables."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from semflow_contracts.common import ArtifactRef, Contract, Digest, digest
from semflow_contracts.rule_values import (
    CollectionRef,
    CorpusSnapshot,
    EmbeddingIdentity,
)
from semflow_contracts.wire import schema_meaning


class CorpusDocument(Contract):
    document_id: UUID
    collection: Literal["reference", "rule_example"]
    version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    language: Literal["python", "javascript", "any"]
    created_at: AwareDatetime
    chunks: tuple[str, ...] = Field(min_length=1)
    provenance: dict
    vectors: tuple[tuple[float, ...] | None, ...] | None = None


class CorpusChunk(Contract):
    chunk_id: UUID
    document_id: UUID
    collection: Literal["reference", "rule_example"]
    version: str = Field(min_length=1)
    position: int = Field(ge=0)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    language: Literal["python", "javascript", "any"]
    created_at: AwareDatetime
    content: ArtifactRef
    provenance: dict
    vector: tuple[float, ...] | None = None


class CorpusManifest(Contract):
    # Interface peers: public.corpus.freeze -> runtime.corpus_inputs.materialize.
    # AGENT: preserve complete ordered chunks, source versions, collection and
    # validation provenance. A new snapshot cannot silently mean a live DB query.
    model_config = ConfigDict(json_schema_extra=schema_meaning("corpus"))
    schema_version: Literal["semflow.research.corpus/1"] = "semflow.research.corpus/1"
    snapshot_id: UUID
    collections: tuple[CollectionRef, ...]
    chunks: tuple[CorpusChunk, ...]
    embedding: EmbeddingIdentity | None = None

    @model_validator(mode="after")
    def complete_documents(self):
        if len({chunk.chunk_id for chunk in self.chunks}) != len(self.chunks):
            raise ValueError("Frozen corpus chunk IDs cannot repeat")
        documents = {}
        for chunk in self.chunks:
            documents.setdefault(chunk.document_id, []).append(chunk)
        for rows in documents.values():
            rows.sort(key=lambda row: row.position)
            if [row.position for row in rows] != list(range(len(rows))):
                raise ValueError(
                    "Frozen document chunks must be complete and contiguous"
                )
            keys = (
                "collection",
                "version",
                "title",
                "source",
                "language",
                "created_at",
                "provenance",
            )
            if any(
                any(getattr(row, key) != getattr(rows[0], key) for key in keys)
                for row in rows
            ):
                raise ValueError("Frozen document metadata changes between chunks")
        if {row.name for row in self.collections} != {
            "reference",
            "rule_example",
        } or len(self.collections) != 2:
            raise ValueError("Frozen rule corpus requires the two explicit collections")
        for collection in self.collections:
            rows = [
                chunk for chunk in self.chunks if chunk.collection == collection.name
            ]
            if set(collection.document_ids) != {row.document_id for row in rows}:
                raise ValueError("Corpus collection membership differs from its chunks")
        if (
            any(chunk.vector is not None for chunk in self.chunks)
            and self.embedding is None
        ):
            raise ValueError("Frozen vectors require an explicit embedding identity")
        if self.embedding and (
            not any(chunk.vector is not None for chunk in self.chunks)
            or any(
                chunk.vector is not None
                and (
                    len(chunk.vector) != self.embedding.dimensions
                    or not any(chunk.vector)
                )
                for chunk in self.chunks
            )
        ):
            raise ValueError(
                "Frozen vectors must match the declared dimension and be nonzero"
            )
        if self.embedding and self.embedding.index_digest != vector_digest(self.chunks):
            raise ValueError(
                "Frozen vector matrix differs from its declared index digest"
            )
        for collection in self.collections:
            if collection.digest != collection_digest(
                [row for row in self.chunks if row.collection == collection.name]
            ):
                raise ValueError(
                    "Frozen collection digest differs from its complete chunks"
                )
        return self


class CorpusCapture(Contract):
    """Local immutable capture identity, not a live corpus visibility record."""

    # Interface peers: public.corpus.freeze / existing_capture.
    # AGENT: request, owner and snapshot identity must remain bound; changing
    # capture semantics requires updating both sides rather than overwriting history.

    schema_version: Literal["semflow.corpus-capture/1"] = "semflow.corpus-capture/1"
    request_digest: Digest
    owner_execution_id: UUID
    snapshot: CorpusSnapshot


def collection_digest(chunks):
    # Both freeze and import use this exact ordered projection; metadata and
    # complete content references participate, not just the visible document IDs.
    return digest(
        [
            chunk.model_dump(mode="json")
            for chunk in sorted(
                chunks, key=lambda row: (str(row.document_id), row.position)
            )
        ]
    )


def vector_digest(chunks):
    return digest(
        [
            {
                "document_id": str(row.document_id),
                "version": row.version,
                "position": row.position,
                "content_sha256": row.content.sha256,
                "vector": row.vector,
            }
            for row in sorted(
                chunks, key=lambda row: (str(row.document_id), row.position)
            )
        ]
    )
