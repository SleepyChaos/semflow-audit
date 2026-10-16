"""Runtime scheduling preserves explicit gaps; patches never edit unseen code."""

from types import SimpleNamespace

import pytest
from app.adapters.project_map import build_project_map
from app.adapters.repair.patches import apply_changes
from app.adapters.scout_scheduling import deferred_reason, focused_tasks
from app.contracts.stages import ProposedChange
from app.domain.audit import AuditError
from app.services.repair_inputs import patch_context, verify_visible_changes


def test_static_fixture_is_deferred_but_runtime_xml_and_test_code_remain():
    assert deferred_reason("tests/fixtures/hosts.xml")
    assert deferred_reason("docs/conf.py")
    assert deferred_reason("examples/client.py")
    assert deferred_reason("config/runtime.xml") is None
    assert deferred_reason("tests/test_parser.py") is None
    assert deferred_reason("package/parser.py") is None
    assert [t["id"] for t in focused_tasks("configuration", True)] == ["secrets_config"]
    assert "input_injection" in {t["id"] for t in focused_tasks("source", True)}


def test_map_deferral_is_auditable_not_safe_or_inspected(tmp_path):
    for file in ("tests/fixtures/hosts.xml", "app.py"):
        p = tmp_path / file
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("value = 1\n")
    evidence = SimpleNamespace(
        root=tmp_path,
        files=lambda: sorted(tmp_path.rglob("*.*")),
        allowed=lambda name: tmp_path / name,
        audit=SimpleNamespace(language="python", snapshot_hash="fixed"),
    )
    original = build_project_map(evidence, 100)
    focused = build_project_map(evidence, 100, scheduling_profile="runtime_first")
    assert len(original["units"]) == 2
    assert [r["file"] for r in focused["units"]] == ["app.py"]
    assert "deferred_static_test_data" in focused["skipped"][0]["reason"]
    assert len(focused["files"]) == 2


def test_large_target_has_exact_windows_and_preserves_rest(tmp_path):
    text = "".join(f"value_{i} = {i}\n" for i in range(3000))
    (tmp_path / "app.py").write_text(text)
    evidence = SimpleNamespace(root=tmp_path)
    materials = [
        {
            "kind": "code",
            "reference": {"file": "app.py", "start_line": 1500, "end_line": 1550},
        }
    ]
    contents, views = patch_context(evidence, ["app.py"], materials)
    assert not views["app.py"]["complete"]
    assert views["app.py"]["segments"][0]["start_line"] == 1500
    assert "value_1499 = 1499" in contents["app.py"]
    change = SimpleNamespace(file="app.py", old_text="value_1499 = 1499")
    verify_visible_changes([change], views)
    replacement = ProposedChange(
        file="app.py",
        old_text=change.old_text,
        new_text="value_1499 = 0",
        reason="Replace only the supplied vulnerable expression",
    )
    destination = tmp_path.parent / (tmp_path.name + "-candidate")
    apply_changes(tmp_path, destination, [replacement], ["app.py"])
    assert (destination / "app.py").read_text() == text.replace(
        change.old_text, replacement.new_text
    )
    change.old_text = "value_1 = 1"
    with pytest.raises(AuditError, match="精确源码窗口"):
        verify_visible_changes([change], views)
    assert (tmp_path / "app.py").read_text() == text


def test_small_file_is_complete_but_cross_window_replacement_is_rejected(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    contents, views = patch_context(
        SimpleNamespace(root=tmp_path),
        ["a.py"],
        [
            {
                "kind": "code",
                "reference": {"file": "a.py", "start_line": 1, "end_line": 1},
            }
        ],
    )
    assert contents == {"a.py": "x = 1\n"}
    assert views["a.py"]["complete"]
    with pytest.raises(AuditError):
        verify_visible_changes([SimpleNamespace(file="b.py", old_text="x = 1")], views)
