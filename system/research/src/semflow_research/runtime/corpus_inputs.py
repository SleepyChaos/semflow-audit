"""Import a verified corpus into one execution's immutable input namespace."""

from dataclasses import replace

from semflow_contracts.corpus import CorpusManifest, collection_digest
from semflow_contracts.errors import ResearchError

from semflow_research.runtime.bundle_io import freeze_input
from semflow_research.runtime.bundle_reader import (
    authorize_artifacts,
    authorize_records,
)
from semflow_research.state.models import KnowledgeChunk


def materialize(context, snapshot):
    # WIRE-RECV:research.corpus — peer: public.corpus.freeze / CorpusManifest.
    # AGENT: never replace this selected snapshot with latest/visible platform
    # rows. Complete source, collection digests and document versions are semantic.
    ref = snapshot.manifest
    context = replace(context, corpus_snapshot=snapshot)
    if (
        ref.kind != "corpus_manifest"
        or ref.schema_version != "semflow.research.corpus/1"
        or snapshot.digest != ref.sha256
    ):
        raise ResearchError(
            "integrity_error",
            "Corpus reference format or digest differs from its frozen snapshot",
        )
    body = CorpusManifest.model_validate_json(context.artifacts.read(ref))
    if (
        body.snapshot_id != snapshot.snapshot_id
        or body.collections != snapshot.collections
        or body.embedding != snapshot.embedding
    ):
        raise ResearchError(
            "identity_mismatch", "Corpus snapshot header differs from its manifest"
        )
    for collection in body.collections:
        if (
            collection_digest(
                [chunk for chunk in body.chunks if chunk.collection == collection.name]
            )
            != collection.digest
        ):
            raise ResearchError("integrity_error", "Corpus collection digest changed")
    context = authorize_artifacts(
        context, tuple(chunk.content for chunk in body.chunks)
    )
    context = authorize_records(context, (ref.owner_execution_id,))
    embedding_identity = None
    if body.embedding is not None:
        expected = body.embedding
        if (
            context.settings.EMBEDDING_MODEL,
            context.settings.EMBEDDING_REVISION,
            context.settings.EMBEDDING_DIMENSIONS,
        ) != (expected.model, expected.revision, expected.dimensions):
            raise ResearchError(
                "identity_mismatch",
                "Configured embedding resource differs from the corpus snapshot",
            )
        from semflow_research.adapters.retrieval.embedding_identity import (
            embedding_identity as resource_identity,
        )

        embedding_identity = resource_identity(_kernel=context)
    for chunk in body.chunks:
        if chunk.content.owner_execution_id != ref.owner_execution_id:
            raise ResearchError(
                "identity_mismatch",
                "Corpus chunk content belongs to a different frozen input producer",
            )
        content = context.artifacts.read(chunk.content).decode("utf-8")
        freeze_input(
            context,
            KnowledgeChunk(
                id=chunk.chunk_id,
                corpus_scope=body.snapshot_id,
                document_id=chunk.document_id,
                version=chunk.version,
                title=chunk.title,
                source=chunk.source,
                language=chunk.language,
                position=chunk.position,
                created_at=chunk.created_at,
                content=content,
                digest=chunk.content.sha256,
                provenance=chunk.provenance,
                corpus=chunk.collection,
                embedding=list(chunk.vector) if chunk.vector is not None else None,
                embedding_model=body.embedding.model if body.embedding else None,
                embedding_identity=embedding_identity,
            ),
            ref.owner_execution_id,
        )
    context.source_records.update(
        context.spec.source.snapshot_id, corpus_scope=body.snapshot_id
    )
    return replace(context, corpus_snapshot=snapshot)
