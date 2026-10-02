from pathlib import Path
from uuid import UUID

from app.core.audit_config import audit_settings


class ArtifactStore:
    def directory(self, run_id: str) -> Path:
        identifier = str(UUID(run_id))
        directory = audit_settings.ARTIFACT_ROOT / "runs" / identifier
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def source(self, run_id: str) -> Path:
        return self.directory(run_id) / "source"

    def log_tail(self, run_id: str) -> str:
        path = self.directory(run_id) / "execution.log"
        if not path.exists():
            return ""
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 30000))
            return stream.read().decode("utf-8", errors="replace")
