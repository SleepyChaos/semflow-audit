"""Moving source must preserve runtime storage and immutable research evidence."""

import hashlib
import json
from pathlib import Path

from app.core.audit_config import ROOT, AuditSettings
from app.core.config import Settings

REPOSITORY = Path(__file__).resolve().parents[2]


def test_runtime_keeps_original_environment_and_artifact_locations():
    assert ROOT == REPOSITORY
    assert AuditSettings.model_config["env_file"] == REPOSITORY / ".env"
    assert Settings.model_config["env_file"] == REPOSITORY / ".env"
    assert (
        AuditSettings.model_fields["ARTIFACT_ROOT"].default == REPOSITORY / "artifacts"
    )
    assert (
        AuditSettings.model_fields["CODEQL_PACK_PATH"].default
        == REPOSITORY / "artifacts/packs"
    )


def test_relocation_preserves_frozen_receipts_papers_bundles_and_lockfiles():
    rows = json.loads((REPOSITORY / "design/repository-file-map.json").read_text())[
        "files"
    ]
    protected = [
        row
        for row in rows
        if row["path"].startswith("benchmarks/testing/20261009-workspace-")
        or row["path"].endswith((".pdf", ".tar.gz", "uv.lock", "package-lock.json"))
    ]
    assert protected
    for row in protected:
        path = REPOSITORY / row["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == row["original_sha256"], row["path"]
