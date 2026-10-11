"""Verify research publication preserves tasks and refuses unsafe restoration."""

import io
import json
import tarfile
from unittest.mock import patch

import pytest

from scripts.benchmarks import archive_research_materials as archive


def bundle_fixture(root, payload=b'{"tasks": [1, 2]}', name="raw/repair/tasks.json"):
    destination = root / "benchmarks/datasets/example.tar.gz"
    destination.parent.mkdir(parents=True)
    with tarfile.open(destination, "w:gz") as packed:
        member = tarfile.TarInfo(name)
        member.size = len(payload)
        member.mode = 0o644
        packed.addfile(member, io.BytesIO(payload))
    data = destination.read_bytes()
    return {
        "summary": {},
        "bundles": [
            {
                "path": destination.relative_to(root).as_posix(),
                "bytes": len(data),
                "sha256": archive.digest(data),
                "files": [
                    {
                        "path": name,
                        "bytes": len(payload),
                        "sha256": archive.digest(payload),
                    }
                ],
            }
        ],
    }


def test_embedded_private_key_redaction_retains_task_and_label():
    key = "-----BEGIN PRIVATE KEY-----\nexample\n-----END PRIVATE KEY-----"
    data = json.dumps([{"task_id": "one", "vulnerable": True, "code": key}]).encode()
    sanitized, changes = archive.public_copy("tasks.json", data)
    assert changes == 1
    assert json.loads(sanitized) == [
        {"task_id": "one", "vulnerable": True, "code": "[REDACTED_PRIVATE_KEY]"}
    ]
    assert "example" in json.loads(data)[0]["code"]
    assert archive.transport_reason("tasks.json", sanitized) is None


def test_benign_input_is_byte_identical():
    data = b'{"id": "one", "expected": false, "source": "return value"}\n'
    assert archive.public_copy("tasks.json", data) == (data, 0)


def test_flask_commit_paths_are_not_mistaken_for_credentials():
    data = json.dumps({"source": "flask-" + "a" * 40 + "/app.py"}).encode()
    assert archive.public_copy("paths.json", data) == (data, 0)


def test_nested_transport_with_key_is_rejected():
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as packed:
        member = tarfile.TarInfo("source/tests/server.key")
        member.size = 7
        packed.addfile(member, io.BytesIO(b"example"))
    assert archive.transport_reason("source.tar.gz", output.getvalue()) == (
        "archive_contains_key_or_execution_artifact"
    )


def test_restore_is_idempotent_and_refuses_changed_existing_input(tmp_path):
    manifest = bundle_fixture(tmp_path)
    with (
        patch.object(archive, "ROOT", tmp_path),
        patch.object(archive, "BENCH", tmp_path / "benchmarks"),
    ):
        archive.verify_or_restore(manifest, restore=True)
        archive.verify_or_restore(manifest, restore=True)
        path = tmp_path / "benchmarks/raw/repair/tasks.json"
        assert json.loads(path.read_text()) == {"tasks": [1, 2]}
        path.write_text('{"tasks": [3]}')
        with pytest.raises(ValueError, match="refusing overwrite"):
            archive.verify_or_restore(manifest, restore=True)
        assert json.loads(path.read_text()) == {"tasks": [3]}


def test_restore_rejects_traversal_before_writing(tmp_path):
    manifest = bundle_fixture(tmp_path, name="../outside.json")
    with (
        patch.object(archive, "ROOT", tmp_path),
        patch.object(archive, "BENCH", tmp_path / "benchmarks"),
        pytest.raises(ValueError, match="Unexpected archive member"),
    ):
        archive.verify_or_restore(manifest, restore=True)
    assert not (tmp_path / "outside.json").exists()


def test_member_checksum_mismatch_is_not_restored(tmp_path):
    manifest = bundle_fixture(tmp_path)
    manifest["bundles"][0]["files"][0]["sha256"] = "0" * 64
    with (
        patch.object(archive, "ROOT", tmp_path),
        patch.object(archive, "BENCH", tmp_path / "benchmarks"),
        pytest.raises(ValueError, match="Member checksum mismatch"),
    ):
        archive.verify_or_restore(manifest, restore=True)
    assert not (tmp_path / "benchmarks/raw/repair/tasks.json").exists()


def test_restore_rejects_existing_directory_symlink(tmp_path):
    manifest = bundle_fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    bench = tmp_path / "benchmarks"
    (bench / "raw").symlink_to(outside, target_is_directory=True)
    with (
        patch.object(archive, "ROOT", tmp_path),
        patch.object(archive, "BENCH", bench),
        pytest.raises(ValueError, match="Unsafe restoration path"),
    ):
        archive.verify_or_restore(manifest, restore=True)
    assert not (outside / "repair/tasks.json").exists()
