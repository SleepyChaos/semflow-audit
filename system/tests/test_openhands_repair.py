"""OpenHands cannot export foreign edits, unchanged runtime logic or external links."""

import json

import pytest
from app.adapters.repair.agent_workspace import (
    export_candidate,
    retain_source,
    writable_copy,
)
from app.adapters.snapshot import snapshot_digest
from app.contracts.stages import RepairRequest
from app.domain.audit import AuditError


def source(tmp_path):
    root = tmp_path / "original"
    root.mkdir()
    (root / "app.py").write_text("value = eval(input())\n")
    (root / "helper.py").write_text("answer = 42\n")
    (root / "tests").mkdir()
    (root / "tests/test_app.py").write_text("def test_normal(): assert True\n")
    return root


def test_effective_candidate_is_exported_without_mutating_original(tmp_path):
    original = source(tmp_path)
    before = snapshot_digest(original)
    workspace = tmp_path / "candidate"
    writable_copy(original, workspace)
    (workspace / "app.py").write_text("value = int(input())\n")
    proposal, patch = export_candidate(
        original, workspace, ["app.py"], "用显式转换保留正常行为并去掉动态执行"
    )
    assert proposal.changes[0].old_text == "value = eval(input())\n"
    assert "+value = int(input())" in patch
    assert snapshot_digest(original) == before


@pytest.mark.parametrize("name", ["helper.py", "tests/test_app.py", ".env"])
def test_unauthorized_test_or_secret_change_is_rejected(tmp_path, name):
    original = source(tmp_path)
    workspace = tmp_path / "candidate"
    writable_copy(original, workspace)
    (workspace / name).write_text("changed = 1\n")
    with pytest.raises(AuditError, match="unauthorized"):
        export_candidate(original, workspace, ["app.py"], "测试不应被接纳为修复")


@pytest.mark.parametrize(
    "replacement", ["value = eval(input())\n", "# fixed now\nvalue = eval(input())\n"]
)
def test_unchanged_or_comment_only_candidate_does_not_count_as_repair(
    tmp_path, replacement
):
    original = source(tmp_path)
    workspace = tmp_path / "candidate"
    writable_copy(original, workspace)
    (workspace / "app.py").write_text(replacement)
    with pytest.raises(AuditError):
        export_candidate(original, workspace, ["app.py"], "注释不能证明漏洞已修复")


def test_safe_document_alias_is_retained_without_following_external_links(tmp_path):
    original = source(tmp_path)
    (original / "AGENTS.md").write_text("untrusted repository instructions")
    (original / "CLAUDE.md").symlink_to("AGENTS.md")
    result = retain_source(original, tmp_path / "retained")
    assert not (tmp_path / "retained/CLAUDE.md").is_symlink()
    assert result["normalized_document_aliases"] == [
        {"file": "CLAUDE.md", "target": "AGENTS.md"}
    ]
    outside = tmp_path / "outside.md"
    outside.write_text("must not be copied")
    (original / "CLAUDE.md").unlink()
    (original / "CLAUDE.md").symlink_to(outside)
    with pytest.raises(AuditError, match="Unsupported"):
        retain_source(original, tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()


def test_engine_is_explicit_and_native_default_remains():
    from uuid import uuid4

    base = {"candidate_ids": [uuid4()]}
    assert RepairRequest(**base).engine == "native"
    assert RepairRequest(**base, engine="openhands").engine == "openhands"


def test_upstream_patch_hypothesis_is_not_promoted_into_engine_requirements():
    from app.services.repair_openhands import source_observations

    view = {
        "modification_semantics": "Preserve unsafe raw HTML because it seems intended",
        "facts": [
            {
                "statement": "content is interpolated",
                "state": "supported",
                "category": "implementation",
                "evidence_ids": ["observed"],
            },
            {
                "statement": "raw HTML must remain allowed",
                "state": "inferred",
                "category": "implementation",
                "evidence_ids": ["hypothesis"],
            },
        ],
        "unknowns": ["other callers"],
    }
    actual = source_observations(view)
    assert actual["facts"] == [view["facts"][0]]
    assert "modification_semantics" not in actual
    assert "raw HTML must remain" not in json.dumps(actual)
    assert actual["unknowns"] == ["other callers"]


@pytest.mark.integration
def test_real_sandbox_only_authorized_existing_source_is_writable(tmp_path):
    import os
    import subprocess

    from app.adapters.repair.openhands import start_sandbox
    from app.adapters.repair.verification_runner import docker_env

    if os.environ.get("AUDIT_RUN_REAL_TOOLS") != "1":
        pytest.skip("requires task-owned Docker sandbox")
    original = source(tmp_path)
    workspace = tmp_path / "candidate"
    writable_copy(original, workspace, ["app.py"])
    name = start_sandbox(
        workspace,
        {
            "image_id": "sha256:bc44a3562c97141e1ccec9a413c2a17193a2f27f30a2bd1f85ab53cc25b055bb"
        },
    )
    script = """from pathlib import Path
Path("app.py").write_text("value = 1\\n")
for name in ("helper.py", ".", "tests"):
    try:
        Path(name).chmod(0o777)
    except PermissionError:
        continue
    raise AssertionError("unauthorized chmod accepted: " + name)
for name in ("helper.py", "tests/test_app.py", "new.py"):
    try:
        Path(name).write_text("bad\\n")
    except PermissionError:
        continue
    raise AssertionError("unauthorized write accepted: " + name)
"""
    try:
        result = subprocess.run(
            ["docker", "exec", name, "python", "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
            env=docker_env(),
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert (workspace / "app.py").read_text() == "value = 1\n"
        assert (workspace / "helper.py").read_text() == "answer = 42\n"
        assert (original / "app.py").read_text() == "value = eval(input())\n"
    finally:
        subprocess.run(
            ["docker", "rm", "-f", name],
            capture_output=True,
            timeout=20,
            env=docker_env(),
            check=False,
        )


def test_large_source_exports_small_hunks_that_replay_exactly(tmp_path):
    from app.adapters.repair.patches import apply_changes

    original = source(tmp_path)
    text = "\n".join(f"field_{i} = {i}" for i in range(1200)) + "\n"
    (original / "app.py").write_text(text)
    workspace = tmp_path / "candidate"
    writable_copy(original, workspace)
    expected = text.replace("field_600 = 600", "field_600 = 601")
    (workspace / "app.py").write_text(expected)
    proposal, _ = export_candidate(
        original, workspace, ["app.py"], "修改大文件时只导出可精确应用的必要窗口"
    )
    assert len(json.dumps(proposal.model_dump())) < 1000
    apply_changes(original, tmp_path / "replayed", proposal.changes, ["app.py"])
    assert (tmp_path / "replayed/app.py").read_text() == expected


def test_many_same_file_edits_fit_schema_and_replay_every_byte(tmp_path):
    from app.adapters.repair.patches import apply_changes

    original = source(tmp_path)
    text = "".join(f"field_{i} = {i}\n" for i in range(400))
    (original / "app.py").write_text(text)
    workspace = tmp_path / "candidate"
    writable_copy(original, workspace)
    expected = text
    for i in range(10, 310, 30):
        expected = expected.replace(f"field_{i} = {i}\n", f"field_{i} = {i + 1}\n")
    (workspace / "app.py").write_text(expected)
    proposal, _ = export_candidate(
        original,
        workspace,
        ["app.py"],
        "合并窗口只调整补丁表示，不减少或更改任何实际修改",
    )
    assert len(proposal.changes) == 8
    apply_changes(original, tmp_path / "replayed", proposal.changes, ["app.py"])
    assert (tmp_path / "replayed/app.py").read_text() == expected


def test_more_changed_files_than_schema_supports_is_explicit_task_failure(tmp_path):
    original = source(tmp_path)
    names = [f"file_{i}.py" for i in range(9)]
    for name in names:
        (original / name).write_text("value = 1\n")
    workspace = tmp_path / "candidate"
    writable_copy(original, workspace)
    for name in names:
        (workspace / name).write_text("value = 2\n")
    with pytest.raises(AuditError) as captured:
        export_candidate(
            original, workspace, names, "无法表达的候选必须明确失败，不能丢弃一部分改动"
        )
    assert captured.value.code == "candidate_export_failed"


def test_monitor_ignores_rotating_sdk_state_and_tracks_actual_events(tmp_path):
    import os
    import time

    from app.adapters.repair.openhands import latest_progress

    stable = tmp_path / "progress.json"
    stable.write_text('{"events": 3}')
    old = time.time() - 280
    os.utime(stable, (old, old))
    internal = tmp_path / "conversation/private-state.tmp"
    internal.parent.mkdir()
    internal.write_text("rotating SDK state")
    assert latest_progress(tmp_path) == pytest.approx(old)
    internal.unlink()
    assert latest_progress(tmp_path) == pytest.approx(old)
    stable.write_text('{"events": 4}')
    assert latest_progress(tmp_path) > old + 200


def test_iteration_exhaustion_rejects_partial_candidate_as_task_failure(
    tmp_path, monkeypatch
):
    import io
    import sys
    from types import SimpleNamespace

    from app.adapters.repair import openhands

    original = source(tmp_path)
    directory = tmp_path / "stage/openhands"

    class ExhaustedProcess:
        returncode = 1

        def __init__(self, *args, **kwargs):
            self.stdin = io.BytesIO()
            (directory / "runtime-result.json").write_text(
                json.dumps({"status": "failed", "error_code": "MaxIterationsReached"})
            )

        def poll(self):
            return 1

    monkeypatch.setattr(openhands.audit_settings, "OPENHANDS_PYTHON", sys.executable)
    monkeypatch.setattr(openhands, "start_sandbox", lambda *a: "owned-test")
    monkeypatch.setattr(openhands.subprocess, "Popen", ExhaustedProcess)
    monkeypatch.setattr(
        openhands.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0)
    )
    with pytest.raises(AuditError) as captured:
        openhands.generate(
            original,
            ["app.py"],
            directory,
            {"model": "test", "base_url": "https://example.invalid"},
            "repair",
        )
    assert captured.value.code == "candidate_iteration_limit"
    assert not (directory / "candidate.json").exists()
    assert (original / "app.py").read_text() == "value = eval(input())\n"
