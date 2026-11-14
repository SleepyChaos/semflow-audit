"""Use the actual BM25/reassembly adapter on an explicit immutable corpus."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from semflow_contracts.corpus import CorpusDocument, CorpusManifest
from semflow_contracts.errors import ResearchError
from semflow_research.adapters.retrieval.dual_corpus import complete_document
from semflow_research.adapters.retrieval.knowledge import KnowledgeRetriever
from semflow_research.public.corpus import freeze
from semflow_research.public.runtime import prepare
from semflow_research.runtime.bundle_reader import authorize_artifacts
from semflow_research.runtime.corpus_inputs import materialize
from semflow_research.state.models import KnowledgeChunk


def documents():
    now = datetime.now(UTC)
    return tuple(
        CorpusDocument(
            document_id=uuid4(),
            collection=collection,
            version="frozen-v1",
            title="CodeInjectionQuery"
            if collection == "reference"
            else "Eval injection example",
            source="explicit:" + collection,
            language="python",
            created_at=now,
            chunks=("CodeQL eval injection evidence reference",)
            if collection == "reference"
            else (
                "/** Complete eval injection query header */",
                "import python\nfrom Call c select c",
            ),
            provenance={
                "api_version": "frozen-api",
                "cwe": "CWE-095",
                "validation": {"status": "passed", "kind": "compile_only"},
            },
        )
        for collection in ("reference", "rule_example")
    )


def test_actual_bm25_uses_only_frozen_chunks_and_assembles_complete_examples(
    research_case, settings
):
    case = research_case
    snapshot = freeze(documents(), root=case.ledger.root, owner_execution_id=uuid4())
    context = prepare(case.spec, root=case.ledger.root, settings=settings)
    context = authorize_artifacts(context, (snapshot.manifest,))
    context = materialize(context, snapshot)
    rows = KnowledgeRetriever(_kernel=context).retrieve(
        snapshot.snapshot_id,
        "python",
        "eval injection",
        mode="bm25",
        corpus="rule_example",
        api_version="frozen-api",
        active_only=True,
    )
    assert rows and rows[0]["methods"] == ["haystack_bm25"]
    assembled = complete_document(snapshot.snapshot_id, rows[0], _kernel=context)
    assert (
        assembled["content"]
        == "/** Complete eval injection query header */\n\nimport python\nfrom Call c select c"
    )
    assert len(assembled["document_chunks"]) == 2
    assert (
        KnowledgeRetriever(_kernel=context).retrieve(
            snapshot.snapshot_id, "javascript", "eval injection", mode="bm25"
        )
        == []
    )
    assert (
        KnowledgeRetriever(_kernel=context).retrieve(
            snapshot.snapshot_id,
            "python",
            "eval injection",
            mode="bm25",
            api_version="different-api",
        )
        == []
    )
    assert len(context.records.list(KnowledgeChunk)) == 3
    assert len(materialize(context, snapshot).records.list(KnowledgeChunk)) == 3


def test_corpus_chunk_tampering_is_rejected_before_retrieval(research_case, settings):
    case = research_case
    snapshot = freeze(
        documents(), root=case.ledger.root, owner_execution_id=case.execution_id
    )
    body = CorpusManifest.model_validate_json(case.artifacts.read(snapshot.manifest))
    chunk = body.chunks[0]
    (case.artifacts.root / str(case.execution_id) / chunk.content.path).write_bytes(
        b"changed source"
    )
    context = prepare(case.spec, root=case.ledger.root, settings=settings)
    with pytest.raises(ResearchError, match="Artifact bytes"):
        materialize(context, snapshot)


def test_frozen_document_and_collection_membership_cannot_be_relabelled(research_case):
    case = research_case
    snapshot = freeze(
        documents(), root=case.ledger.root, owner_execution_id=case.execution_id
    )
    body = CorpusManifest.model_validate_json(case.artifacts.read(snapshot.manifest))
    changed = body.model_dump(mode="json")
    changed["chunks"][1]["position"] = 7
    with pytest.raises(ValidationError, match="complete and contiguous"):
        CorpusManifest.model_validate(changed)
    changed = body.model_dump(mode="json")
    changed["collections"][0]["digest"] = "0" * 64
    with pytest.raises(ValidationError, match="collection digest"):
        CorpusManifest.model_validate(changed)
    old = documents()[0]
    newer = old.model_copy(update={"document_id": uuid4(), "version": "other-version"})
    with pytest.raises(ValueError, match="active source version"):
        freeze(
            (old, newer), root=case.ledger.root, owner_execution_id=case.execution_id
        )


def test_snapshot_id_is_idempotent_and_cannot_be_reused_for_changed_content(
    research_case,
):
    case = research_case
    source = documents()
    identifier = uuid4()
    first = freeze(
        source,
        root=case.ledger.root,
        owner_execution_id=case.execution_id,
        snapshot_id=identifier,
    )
    assert (
        freeze(
            source,
            root=case.ledger.root,
            owner_execution_id=case.execution_id,
            snapshot_id=identifier,
        )
        == first
    )
    changed = (
        source[0].model_copy(update={"chunks": ("different content",)}),
        source[1],
    )
    with pytest.raises(ResearchError, match="already frozen"):
        freeze(
            changed,
            root=case.ledger.root,
            owner_execution_id=case.execution_id,
            snapshot_id=identifier,
        )
    assert (
        freeze(
            source,
            root=case.ledger.root,
            owner_execution_id=case.execution_id,
            snapshot_id=identifier,
        )
        == first
    )


def test_partially_indexed_corpus_retains_bm25_chunks_and_binds_vector_holes(
    research_case, settings
):
    from semflow_research.public.corpus import embedding_for_documents

    source = documents()
    source = (
        source[0].model_copy(update={"vectors": ((1.0, 0.0),)}),
        source[1].model_copy(update={"vectors": ((0.0, 1.0), None)}),
    )
    resources = settings.model_copy(
        update={
            "EMBEDDING_MODEL": "frozen-embed",
            "EMBEDDING_REVISION": "test-v1",
            "EMBEDDING_DIMENSIONS": 2,
        }
    )
    embedding = embedding_for_documents(source, resources)
    case = research_case
    snapshot = freeze(
        source,
        root=case.ledger.root,
        owner_execution_id=case.execution_id,
        embedding=embedding,
    )
    body = CorpusManifest.model_validate_json(case.artifacts.read(snapshot.manifest))
    assert len(body.chunks) == 3 and sum(c.vector is None for c in body.chunks) == 1
    context = materialize(
        prepare(case.spec, root=case.ledger.root, settings=resources), snapshot
    )
    assert len(context.records.list(KnowledgeChunk)) == 3
    changed = body.model_dump(mode="json")
    next(row for row in changed["chunks"] if row["vector"] is None)["vector"] = [
        1.0,
        0.0,
    ]
    with pytest.raises(ValidationError, match="index digest"):
        CorpusManifest.model_validate(changed)
    empty = tuple(doc.model_copy(update={"vectors": None}) for doc in source)
    with pytest.raises(ResearchError, match="indexed chunks"):
        embedding_for_documents(empty, resources)


def test_public_and_workspace_current_documents_remain_distinct(
    research_case, settings
):
    from semflow_research.adapters.retrieval.quality import active_records

    reference, example = documents()
    public = reference.model_copy(
        update={"provenance": {**reference.provenance, "corpus_origin_scope": "public"}}
    )
    workspace = reference.model_copy(
        update={
            "document_id": uuid4(),
            "version": "workspace-v2",
            "provenance": {**reference.provenance, "corpus_origin_scope": "workspace"},
        }
    )
    case = research_case
    snapshot = freeze(
        (public, workspace, example),
        root=case.ledger.root,
        owner_execution_id=case.execution_id,
    )
    context = materialize(
        prepare(case.spec, root=case.ledger.root, settings=settings), snapshot
    )
    selected = active_records(context.records.list(KnowledgeChunk))
    assert {row.document_id for row in selected} == {
        public.document_id,
        workspace.document_id,
        example.document_id,
    }
