"""Freeze caller-selected reference/example documents without a platform database."""

import hashlib
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from types import SimpleNamespace
from uuid import UUID, uuid4, uuid5

from semflow_contracts.common import canonical_bytes, digest
from semflow_contracts.corpus import (
    CorpusCapture,
    CorpusChunk,
    CorpusDocument,
    CorpusManifest,
    collection_digest,
    vector_digest,
)
from semflow_contracts.errors import ResearchError
from semflow_contracts.rule_values import (
    CollectionRef,
    CorpusSnapshot,
    EmbeddingIdentity,
)

from semflow_research.runtime.artifacts import LocalArtifacts


def embedding_for_documents(documents, settings):
    """Describe caller-provided vectors; never index, regenerate or drop chunks."""
    # Peer: CorpusManifest.complete_documents / corpus_inputs.materialize.
    # AGENT: None means an unindexed chunk retained for BM25. Bind the complete
    # matrix, including those holes, and require the same query embedding space.
    if not settings.EMBEDDING_MODEL or not settings.EMBEDDING_REVISION:
        raise ResearchError(
            "invalid_contract", "Frozen vectors need model and revision"
        )
    matrix = []
    for doc in documents:
        if doc.vectors is not None and len(doc.vectors) != len(doc.chunks):
            raise ResearchError("invalid_contract", "Frozen vector/chunk count differs")
        for position, text in enumerate(doc.chunks):
            matrix.append(
                SimpleNamespace(
                    document_id=doc.document_id,
                    version=doc.version,
                    position=position,
                    content=SimpleNamespace(
                        sha256=hashlib.sha256(text.encode()).hexdigest()
                    ),
                    vector=doc.vectors[position] if doc.vectors else None,
                )
            )
    if not any(row.vector is not None for row in matrix):
        raise ResearchError("invalid_contract", "Vector retrieval needs indexed chunks")
    return EmbeddingIdentity(
        provider="openai-compatible",
        model=settings.EMBEDDING_MODEL,
        revision=settings.EMBEDDING_REVISION,
        dimensions=settings.EMBEDDING_DIMENSIONS,
        index_digest=vector_digest(matrix),
    )


def freeze(
    documents,
    *,
    root,
    owner_execution_id: UUID,
    snapshot_id=None,
    version="1",
    embedding=None,
):
    documents = tuple(
        CorpusDocument.model_validate_json(document.model_dump_json())
        for document in documents
    )
    if len({document.document_id for document in documents}) != len(documents):
        raise ValueError(
            "Corpus snapshot requires one explicitly selected version per document ID"
        )
    versions = {}
    for document in documents:
        # Peer: platform rule_corpus.capture declares public/workspace origin.
        # AGENT: independently visible sources may share a name; preserve their
        # declared scope rather than silently dropping one owner's current data.
        key = (
            document.collection,
            document.source,
            document.language,
            document.provenance.get("corpus_origin_scope"),
        )
        if key in versions and versions[key] != document.version:
            raise ValueError(
                "Select one active source version before freezing the corpus snapshot"
            )
        versions[key] = document.version
    snapshot_id = snapshot_id or uuid4()
    memo = root / "corpora" / str(snapshot_id) / "capture.json"
    for path in (root, root / "corpora", memo.parent, memo):
        if path.is_symlink():
            raise ResearchError(
                "integrity_error", "Corpus capture path cannot be a symlink"
            )
    request_digest = digest(
        {
            "owner_execution_id": str(owner_execution_id),
            "documents": [document.model_dump(mode="json") for document in documents],
            "version": version,
            "embedding": embedding.model_dump(mode="json") if embedding else None,
        }
    )
    artifacts = LocalArtifacts(root / "artifacts", owner_execution_id)
    if memo.exists():
        return existing_capture(
            memo, request_digest, owner_execution_id, snapshot_id, artifacts
        )
    chunks = []
    for document in documents:
        if document.vectors is not None and len(document.vectors) != len(
            document.chunks
        ):
            raise ValueError("Frozen vector/chunk count differs")
        for position, text in enumerate(document.chunks):
            content = artifacts.commit(
                text.encode(),
                kind="materials",
                schema_version="semflow.corpus-text/1",
                media_type="text/plain",
            )
            chunks.append(
                CorpusChunk(
                    chunk_id=uuid5(
                        snapshot_id,
                        f"{document.document_id}/{document.version}/{position}/{content.sha256}",
                    ),
                    document_id=document.document_id,
                    collection=document.collection,
                    version=document.version,
                    position=position,
                    title=document.title,
                    source=document.source,
                    language=document.language,
                    created_at=document.created_at,
                    content=content,
                    provenance=document.provenance,
                    vector=document.vectors[position] if document.vectors else None,
                )
            )
    collections = tuple(
        CollectionRef(
            name=name,
            version=version,
            document_ids=tuple(
                sorted(
                    {chunk.document_id for chunk in chunks if chunk.collection == name},
                    key=str,
                )
            ),
            digest=collection_digest(
                [chunk for chunk in chunks if chunk.collection == name]
            ),
        )
        for name in ("reference", "rule_example")
    )
    body = CorpusManifest(
        snapshot_id=snapshot_id,
        collections=collections,
        chunks=tuple(chunks),
        embedding=embedding,
    )
    # WIRE-SEND:research.corpus — peer: runtime.corpus_inputs.materialize.
    # AGENT: the byte digest covers all chunks, vectors and provenance; retain
    # corpus/collection identity and complete source text in the receiving adapter.
    ref = artifacts.commit(
        canonical_bytes(body),
        kind="corpus_manifest",
        schema_version=body.schema_version,
    )
    snapshot = CorpusSnapshot(
        snapshot_id=snapshot_id,
        manifest=ref,
        digest=ref.sha256,
        collections=collections,
        embedding=embedding,
    )
    capture = CorpusCapture(
        request_digest=request_digest,
        owner_execution_id=owner_execution_id,
        snapshot=snapshot,
    )
    memo.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=memo.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(canonical_bytes(capture))
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(temporary, memo)
    except FileExistsError:
        return existing_capture(
            memo, request_digest, owner_execution_id, snapshot_id, artifacts
        )
    finally:
        temporary.unlink(missing_ok=True)
    return snapshot


def existing_capture(path, request_digest, owner_execution_id, snapshot_id, artifacts):
    # WIRE-RECV:research.corpus — peer: freeze's capture commit and materialize.
    # AGENT: a repeated snapshot ID must keep the same frozen request and owner;
    # never overwrite history with a new "current" manifest under the same ID.
    captured = CorpusCapture.model_validate_json(path.read_bytes())
    if (
        captured.request_digest != request_digest
        or captured.owner_execution_id != owner_execution_id
        or captured.snapshot.snapshot_id != snapshot_id
        or captured.snapshot.manifest.owner_execution_id != owner_execution_id
    ):
        raise ResearchError(
            "execution_conflict",
            "Corpus snapshot ID is already frozen with different inputs or owner",
        )
    body = CorpusManifest.model_validate_json(
        artifacts.read(captured.snapshot.manifest)
    )
    if (
        body.snapshot_id != snapshot_id
        or captured.snapshot.digest != captured.snapshot.manifest.sha256
    ):
        raise ResearchError("integrity_error", "Frozen corpus capture identity changed")
    return captured.snapshot
