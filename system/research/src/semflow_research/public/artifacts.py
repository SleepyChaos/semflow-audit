"""Caller-owned artifact preparation without importing private runtime modules."""

from semflow_research.runtime.artifacts import LocalArtifacts


def commit(
    data, *, root, execution_id, kind, schema_version, media_type="application/json"
):
    return LocalArtifacts(root / "artifacts", execution_id).commit(
        data, kind=kind, schema_version=schema_version, media_type=media_type
    )
