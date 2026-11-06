"""Moving source must preserve runtime storage and immutable research evidence."""

import hashlib
import json
import tomllib
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


def test_relocation_preserves_frozen_receipts_papers_and_bundles():
    rows = json.loads((REPOSITORY / "design/repository-file-map.json").read_text())[
        "files"
    ]
    protected = [
        row
        for row in rows
        if row["path"].startswith("benchmarks/testing/20261009-workspace-")
        or row["path"].endswith((".pdf", ".tar.gz"))
    ]
    assert protected
    for row in protected:
        path = REPOSITORY / row["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == row["original_sha256"], row["path"]


def test_live_dependency_locks_match_their_current_manifests():
    # The relocation map is historical; live dependencies evolve after relocation.
    # CI additionally installs with npm ci and uv sync --locked.
    for directory in ("system/frontend", "system/scripts/tools/codeql-lsp"):
        manifest = json.loads((REPOSITORY / directory / "package.json").read_text())
        lock = json.loads((REPOSITORY / directory / "package-lock.json").read_text())
        assert lock["lockfileVersion"] >= 2
        for group in ("dependencies", "devDependencies"):
            assert lock["packages"][""].get(group, {}) == manifest.get(group, {})
    manifest = tomllib.loads((REPOSITORY / "system/backend/pyproject.toml").read_text())
    lock = tomllib.loads((REPOSITORY / "system/uv.lock").read_text())
    application = next(package for package in lock["package"] if package["name"] == "app")
    assert application["version"] == manifest["project"]["version"]
    assert application["dependencies"]
