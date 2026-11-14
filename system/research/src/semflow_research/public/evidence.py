"""Capture actual source evidence while a caller prepares a typed input bundle."""

from semflow_research.runtime.artifacts import LocalArtifacts
from semflow_research.runtime.evidence import SnapshotReader


def read(snapshot, *, root, source_root, execution_id, path, start_line, end_line):
    store = LocalArtifacts(
        root / "artifacts", execution_id, upstream=(snapshot.archive, snapshot.manifest)
    )
    reader = SnapshotReader(source_root, snapshot, execution_id, store)
    reader.verify_snapshot()
    lines = (reader.root / path).read_text().splitlines()
    return reader.read(path, start_line, min(end_line, len(lines)))
