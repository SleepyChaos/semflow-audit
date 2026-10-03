from uuid import UUID
from sqlmodel import Session
from app.core.db import engine
from app.adapters.retrieval.knowledge import import_knowledge, KnowledgeRetriever
from app.persistence.knowledge_models import KnowledgeChunk


def test_actual_bm25_retrieval_has_versioned_citations(pipeline_context):
    owner = pipeline_context["owner"]
    record = import_knowledge(
        owner,
        "知识检索测试",
        "local-test",
        "python",
        "真实中文检索支持代码规则知识。用于测试的唯一标记 golden_fixture_source 和输入传播保护证据。",
    )
    rows = KnowledgeRetriever().retrieve(
        owner, "python", "golden_fixture_source 中文检索"
    )
    matched = next(row for row in rows if row["document_id"] == record["document_id"])
    assert matched["version"] == record["version"]
    assert matched["methods"] == ["haystack_bm25"]
    assert "golden_fixture_source" in matched["content"]
    assert matched["score"] > 0


def test_knowledge_cannot_leak_between_owners(pipeline_context):
    own = import_knowledge(
        pipeline_context["owner"],
        "Private own",
        "local-test",
        "python",
        "ownership_unique_marker private scoped content for this audit user only.",
    )
    rows = KnowledgeRetriever().retrieve(
        pipeline_context["owner"], "javascript", "ownership_unique_marker"
    )
    assert not any(row["document_id"] == own["document_id"] for row in rows)
    # An unrelated user has access only to shared knowledge, not private chunks.
    from uuid import uuid4

    rows = KnowledgeRetriever().retrieve(uuid4(), "python", "ownership_unique_marker")
    assert not any(row["document_id"] == own["document_id"] for row in rows)


def test_real_pgvector_cosine_retrieval_and_owner_filter(pipeline_context, monkeypatch):
    from app.core.audit_config import audit_settings
    from app.adapters.retrieval import knowledge

    owner = pipeline_context["owner"]
    imported = import_knowledge(
        owner,
        "Vector-only match",
        "local-test",
        "python",
        "A semantically related source modeling passage without the literal search keyword.",
    )
    with Session(engine) as session:
        from sqlmodel import select

        rows = session.exec(
            select(KnowledgeChunk).where(
                KnowledgeChunk.document_id == UUID(imported["document_id"])
            )
        ).all()
        for row in rows:
            row.embedding = [1.0, 0.0, 0.0]
            row.embedding_model = "test-vector-3d"
            session.add(row)
        session.commit()

    class Embedder:
        def embed(self, texts):
            return [[1.0, 0.0, 0.0] for _ in texts]

    monkeypatch.setattr(audit_settings, "EMBEDDING_MODEL", "test-vector-3d")
    monkeypatch.setattr(knowledge, "CompatibleModel", Embedder)
    rows = knowledge.KnowledgeRetriever().retrieve(
        owner, "python", "no_lexical_token_match_98765"
    )
    assert any(row["document_id"] == imported["document_id"] for row in rows)
    assert any("pgvector_cosine_rrf" in row["methods"] for row in rows)
    from uuid import uuid4

    others = knowledge.KnowledgeRetriever().retrieve(
        uuid4(), "python", "no_lexical_token_match_98765"
    )
    assert not any(row["document_id"] == imported["document_id"] for row in others)
