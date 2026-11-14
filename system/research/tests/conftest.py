import hashlib
import io
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4
from zipfile import ZipFile

import pytest
from research_cases import scan_spec
from semflow_contracts.common import (
    SourceFile,
    SourceManifest,
    SourceSnapshot,
    canonical_bytes,
    digest,
)
from semflow_contracts.errors import Failure
from semflow_contracts.results import Completeness, ResultEnvelope, Timestamps, Usage
from semflow_contracts.runs import validate_spec
from semflow_research.runtime.artifacts import LocalArtifacts
from semflow_research.runtime.evidence import SnapshotReader
from semflow_research.runtime.ledger import LocalLedger


@pytest.fixture
def research_case(tmp_path):
    execution_id = uuid4()
    ledger = LocalLedger(tmp_path / "research")
    artifacts = LocalArtifacts(ledger.root / "artifacts", execution_id)
    source = tmp_path / "source"
    source.mkdir()
    content = b"value = eval(input())\n"
    (source / "app.py").write_bytes(content)
    manifest = SourceManifest(
        files=(
            SourceFile(
                path="app.py",
                sha256=hashlib.sha256(content).hexdigest(),
                size_bytes=len(content),
            ),
        )
    )
    manifest_ref = artifacts.commit(
        canonical_bytes(manifest),
        kind="source_manifest",
        schema_version=manifest.schema_version,
    )
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("app.py", content)
    archive_ref = artifacts.commit(
        stream.getvalue(),
        kind="source_archive",
        schema_version="source.zip/1",
        media_type="application/zip",
    )
    snapshot = SourceSnapshot(
        snapshot_id=uuid4(),
        tree_sha256=digest(manifest),
        archive=archive_ref,
        manifest=manifest_ref,
        languages=("python",),
        origin={"kind": "archive"},
    )
    value = scan_spec(execution_id)
    value["source"] = snapshot.model_dump(mode="json")
    spec = validate_spec(value)
    ledger.create(spec)
    reader = SnapshotReader(source, snapshot, execution_id, artifacts)

    def failed_result(**updates):
        now = datetime.now(UTC)
        result = ResultEnvelope(
            execution_id=execution_id,
            input_digest=digest(spec),
            module=spec.module,
            operation=spec.operation,
            implementation=spec.implementation,
            execution_status="failed",
            completeness=Completeness(
                status="none", reasons=("Synthetic parser failure",)
            ),
            result=None,
            failure=Failure(
                code="parse_failed",
                category="tool",
                message="Synthetic invalid SARIF",
                retryable=False,
                phase="parse",
            ),
            usage=Usage(
                calls=0,
                input_tokens=0,
                output_tokens=0,
                wall_seconds=0.1,
                completeness="complete",
            ),
            timestamps=Timestamps(created_at=now, started_at=now, ended_at=now),
        )
        return result.model_copy(update=updates)

    return SimpleNamespace(
        execution_id=execution_id,
        ledger=ledger,
        artifacts=artifacts,
        source=source,
        snapshot=snapshot,
        spec=spec,
        reader=reader,
        failed_result=failed_result,
    )


# Register shared discovery fixtures without importing a test module.
from discovery_cases import scanner, settings  # noqa: F401

from research.tests.native_cases import repair_model, syntax  # noqa: F401
from research.tests.suite_cases import suite_model, suite_runner  # noqa: F401
