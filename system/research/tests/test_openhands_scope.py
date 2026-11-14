"""The external engine has the same read and patch boundaries as native repair."""

import json
from types import SimpleNamespace

import pytest
from semflow_research.adapters.repair.agent_workspace import writable_copy
from semflow_research.domain.errors import AuditError
from semflow_research.evidence.context_materials import digest
from semflow_research.repair.repair_openhands import OpenHandsRepair

from research.tests.openhands_cases import proposal


def test_worker_can_read_declared_directory_but_not_other_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text("value = eval(input())\n")
    (source / "private.py").write_text("unselected source material\n")
    (source / "docs").mkdir()
    (source / "docs/context.md").write_text("Explicitly selected read-only context\n")
    target = tmp_path / "worker"
    writable_copy(source, target, ["app.py"], readable_paths={"app.py", "docs"})
    assert (target / "docs/context.md").read_text().startswith("Explicitly selected")
    with pytest.raises(PermissionError):
        (target / "private.py").read_text()
    with pytest.raises(PermissionError):
        (target / "docs/context.md").write_text("worker must not change this")
    (target / "app.py").write_text("value = int(input())\n")
    assert (source / "app.py").read_text() == "value = eval(input())\n"
    # Restore only the disposable test copy for host cleanup.
    for path in [target, *target.rglob("*")]:
        path.chmod(0o755 if path.is_dir() else 0o644)


@pytest.mark.parametrize("violation", ["unobserved", "file_count"])
def test_openhands_candidate_cannot_bypass_observed_range_or_file_cap(
    tmp_path, violation
):
    candidate = proposal()
    if violation == "file_count":
        candidate["changes"].append({**candidate["changes"][0], "file": "other.py"})
    (tmp_path / "repair-context.json").write_text(
        json.dumps(
            {"file_views": {"app.py": {"segments": [{"content": "observed_call()"}]}}}
        )
    )
    # The target confirmation is tested through the public graph elsewhere;
    # here the receiver must reject the candidate before any patch is applied.
    operation = object.__new__(OpenHandsRepair)
    operation.service = SimpleNamespace(directory=tmp_path)
    operation.semantic = SimpleNamespace(targets=lambda: None)
    operation._kernel = SimpleNamespace(
        spec=SimpleNamespace(
            inputs=SimpleNamespace(patch_scope=SimpleNamespace(max_changed_files=1))
        )
    )
    with pytest.raises(AuditError) as failure:
        operation.apply({"proposal": candidate, "proposal_hash": digest(candidate)})
    assert failure.value.code == "scope_error"
    assert not (tmp_path / "attempt-1/workspace").exists()
