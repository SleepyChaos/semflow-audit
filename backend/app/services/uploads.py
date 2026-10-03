import shutil
from pathlib import Path
from uuid import uuid4

from sqlmodel import Session

from app.adapters.archive import extract_snapshot
from app.adapters.artifacts import ArtifactStore
from app.core.audit_config import audit_settings
from app.persistence.audit_models import AuditRun


def create_run(
    session: Session,
    owner_id,
    archive: Path,
    name: str,
    language: str,
    custom_rule_ids: list[str] | None = None,
) -> AuditRun:
    identifier = uuid4()
    store = ArtifactStore()
    directory = store.directory(str(identifier))
    try:
        shutil.copyfile(archive, directory / "upload.zip")
        snapshot_hash, coverage = extract_snapshot(
            directory / "upload.zip", directory / "source", language
        )
        pack = (
            audit_settings.PYTHON_QUERY_PACK
            if language == "python"
            else audit_settings.JAVASCRIPT_QUERY_PACK
        )
        prefix = "python" if language == "python" else "javascript"
        run = AuditRun(
            id=identifier,
            owner_id=owner_id,
            source_run_id=identifier,
            project_name=name,
            language=language,
            snapshot_hash=snapshot_hash,
            query_pack=pack,
            suite=f"codeql-suites/{prefix}-security-extended.qls",
            coverage=coverage,
            custom_rule_ids=custom_rule_ids or [],
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run
    except Exception:
        session.rollback()
        shutil.rmtree(directory, ignore_errors=True)
        raise
