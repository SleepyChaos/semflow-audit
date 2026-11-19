"""Real source evidence is verified independently of platform persistence."""

import hashlib
from pathlib import Path

from semflow_research.adapters.source_text import decode_source
from uuid import UUID, uuid4

from semflow_contracts.common import (
    SourceLocation,
    SourceManifest,
    SourceSnapshot,
    digest,
    relative_path,
)
from semflow_contracts.errors import ResearchError
from semflow_contracts.evidence import EvidenceProvenance, EvidenceRecord

from semflow_research.runtime.ports import ArtifactStore


class SnapshotReader:
    def __init__(
        self,
        root: Path,
        snapshot: SourceSnapshot,
        execution_id: UUID,
        artifacts: ArtifactStore,
    ):
        if root.is_symlink() or not root.is_dir():
            raise ResearchError(
                "integrity_error",
                "Source root must be an existing directory without symlinks",
            )
        self.root = root.resolve()
        self.snapshot, self.execution_id, self.artifacts = (
            snapshot,
            execution_id,
            artifacts,
        )
        self.manifest = SourceManifest.model_validate_json(
            artifacts.read(snapshot.manifest)
        )
        if digest(self.manifest) != snapshot.tree_sha256:
            raise ResearchError(
                "integrity_error", "Source manifest has the wrong tree identity"
            )
        self.files = {entry.path: entry for entry in self.manifest.files}
        if len(self.files) != len(self.manifest.files):
            raise ResearchError("integrity_error", "Duplicate file in source manifest")
        self.verify_snapshot()

    def verify_snapshot(self) -> None:
        actual = set()
        for path in self.root.rglob("*"):
            if path.is_symlink():
                raise ResearchError(
                    "integrity_error", "Source snapshot contains a symlink"
                )
            if path.is_file():
                name = path.relative_to(self.root).as_posix()
                actual.add(name)
                expected = self.files.get(name)
                content = path.read_bytes()
                if (
                    expected is None
                    or len(content) != expected.size_bytes
                    or hashlib.sha256(content).hexdigest() != expected.sha256
                ):
                    raise ResearchError(
                        "integrity_error", "Source bytes changed or were not frozen"
                    )
        if actual != set(self.files):
            raise ResearchError("integrity_error", "Source snapshot is incomplete")

    def _slice(self, name: str, start: int, end: int) -> bytes:
        try:
            relative_path(name)
        except ValueError as exc:
            raise ResearchError(
                "evidence_invalid", "Source path is outside the snapshot"
            ) from exc
        if name not in self.files or start < 1 or end < start or end - start > 150:
            raise ResearchError(
                "evidence_invalid",
                "Source file or evidence range is outside the snapshot",
            )
        self.verify_snapshot()
        content = (self.root / name).read_bytes()
        if len(content) > 1024 * 1024:
            raise ResearchError(
                "evidence_invalid", "Source file exceeds the evidence read limit"
            )
        try:
            lines = decode_source(self.root / name, content).splitlines()
        except UnicodeError as exc:
            raise ResearchError(
                "evidence_invalid", "Source evidence has no reliable decoding"
            ) from exc
        if end > len(lines):
            raise ResearchError(
                "evidence_invalid", "Source evidence range exceeds actual EOF"
            )
        excerpt = "\n".join(lines[start - 1 : end])
        if len(excerpt) > 12000:
            raise ResearchError(
                "evidence_invalid", "Source excerpt exceeds the evidence read limit"
            )
        return excerpt.encode("utf-8")

    def read(
        self, path: str, start_line: int = 1, end_line: int = 60
    ) -> EvidenceRecord:
        content = self._slice(path, start_line, end_line)
        ref = self.artifacts.commit(
            content,
            kind="source_slice",
            schema_version="semflow.source-slice/1",
            media_type="text/plain",
        )
        # WIRE-SEND:research.evidence — peer: validate / target materialization.
        # The slice uses UTF-8 logical lines; SourceLocation binds the original file bytes.
        # AGENT: keep this projection and the verifier aligned with wire.py.
        return EvidenceRecord(
            evidence_id=uuid4(),
            execution_id=self.execution_id,
            snapshot_id=self.snapshot.snapshot_id,
            kind="code",
            content=ref,
            digest=ref.sha256,
            location=SourceLocation(
                snapshot_id=self.snapshot.snapshot_id,
                path=path,
                start_line=start_line,
                end_line=end_line,
                file_sha256=self.files[path].sha256,
            ),
            provenance=EvidenceProvenance(
                producer="snapshot_reader/1", input_refs=(self.snapshot.manifest,)
            ),
        )

    def validate(self, evidence: EvidenceRecord) -> None:
        # WIRE-RECV:research.evidence — peer: read / imported target bundle producer.
        # AGENT: preserve snapshot, byte/range and upstream scope checks when changing the producer.
        evidence = EvidenceRecord.model_validate_json(evidence.model_dump_json())
        if (
            evidence.snapshot_id != self.snapshot.snapshot_id
            or evidence.kind != "code"
            or evidence.location is None
        ):
            raise ResearchError(
                "evidence_invalid", "Evidence is not code from this snapshot"
            )
        location = evidence.location
        expected = self._slice(location.path, location.start_line, location.end_line)
        if (
            location.file_sha256 != self.files[location.path].sha256
            or self.artifacts.read(evidence.content) != expected
        ):
            raise ResearchError(
                "evidence_invalid", "Evidence does not match the cited source bytes"
            )
