"""Seed versioned project-maintained documentation; imports are idempotent by hash."""

import hashlib
from pathlib import Path
from sqlmodel import Session, select
from app.core.db import engine
from app.persistence.knowledge_models import KnowledgeChunk
from app.adapters.retrieval.knowledge import import_knowledge

root = Path(__file__).resolve().parents[2]
for language in ["python", "javascript"]:
    path = root / "system/knowledge" / f"{language}-codeql.md"
    content = path.read_text()
    version = hashlib.sha256(content.encode()).hexdigest()
    with Session(engine) as session:
        present = session.exec(
            select(KnowledgeChunk).where(
                KnowledgeChunk.owner_id.is_(None), KnowledgeChunk.version == version
            )
        ).first()
    if not present:
        result = import_knowledge(
            None,
            content.splitlines()[0].lstrip("# "),
            "project-maintained:" + path.name,
            language,
            content,
        )
        print(language, result["version"], result["chunks"])
