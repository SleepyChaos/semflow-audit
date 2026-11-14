"""Execution-scoped, content-addressed artifacts with verified upstream access."""

import hashlib
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID, uuid4

from semflow_contracts.common import ArtifactKind, ArtifactRef
from semflow_contracts.errors import ResearchError


class LocalArtifacts:
    def __init__(
        self, root: Path, execution_id: UUID, *, upstream: tuple[ArtifactRef, ...] = ()
    ):
        if root.is_symlink():
            raise ResearchError("integrity_error", "Artifact root cannot be a symlink")
        self.root = root.resolve()
        self.execution_id = execution_id
        self.upstream = frozenset(ref.model_dump_json() for ref in upstream)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _path(self, ref: ArtifactRef) -> Path:
        ref = ArtifactRef.model_validate_json(ref.model_dump_json())
        if (
            ref.owner_execution_id != self.execution_id
            and ref.model_dump_json() not in self.upstream
        ):
            raise ResearchError(
                "identity_mismatch", "Artifact is not an explicit upstream input"
            )
        base = self.root / str(ref.owner_execution_id)
        path = base / ref.path
        for part in (base, *path.parents):
            if part == self.root:
                break
            if part.is_symlink():
                raise ResearchError("integrity_error", "Symlink in artifact path")
        if path.is_symlink() or not path.resolve().is_relative_to(base.resolve()):
            raise ResearchError("integrity_error", "Artifact escaped its execution")
        return path

    def commit(
        self,
        data: bytes,
        *,
        kind: ArtifactKind,
        schema_version: str,
        media_type: str = "application/json",
    ) -> ArtifactRef:
        sha256 = hashlib.sha256(data).hexdigest()
        ref = ArtifactRef(
            artifact_id=uuid4(),
            owner_execution_id=self.execution_id,
            kind=kind,
            schema_version=schema_version,
            path=f"objects/{sha256[:2]}/{sha256}",
            sha256=sha256,
            size_bytes=len(data),
            media_type=media_type,
        )
        target = self._path(ref)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if target.exists():
            if self.read(ref) != data:
                raise ResearchError("integrity_error", "Existing artifact was modified")
            return ref
        temporary = None
        try:
            with NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            # The target name is its byte digest; concurrent equal commits are safe.
            os.link(temporary, target)
        except FileExistsError:
            if self.read(ref) != data:
                raise ResearchError("integrity_error", "Concurrent artifact mismatch")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return ref

    def read(self, ref: ArtifactRef) -> bytes:
        path = self._path(ref)
        try:
            with path.open("rb") as stream:
                data = stream.read(ref.size_bytes + 1)
        except OSError as exc:
            raise ResearchError(
                "integrity_error", "Referenced artifact is unavailable"
            ) from exc
        if (
            len(data) != ref.size_bytes
            or hashlib.sha256(data).hexdigest() != ref.sha256
        ):
            raise ResearchError(
                "integrity_error", "Artifact bytes do not match the reference"
            )
        return data
