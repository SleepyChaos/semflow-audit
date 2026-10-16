"""Navigation packing must not delete evidence or share data across audits."""

import json
from types import SimpleNamespace

from app.adapters.project_navigation import navigation_index
from app.adapters.repair.readiness import target_readiness
from app.adapters.semantic_packing import pack_repair_payload


def test_cache_is_instance_snapshot_and_scope_bound(tmp_path):
    (tmp_path / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n")
    calls = []

    def files():
        calls.append(1)
        return [tmp_path / "app.py"]

    evidence = SimpleNamespace(
        root=tmp_path,
        paths=[],
        files=files,
        allowed=lambda p: tmp_path / p,
        audit=SimpleNamespace(snapshot_hash="one", language="python"),
    )
    first = navigation_index(evidence)
    assert first["python_factories"] == ["app.py"]
    assert navigation_index(evidence) is first
    assert len(calls) == 1
    evidence.audit.snapshot_hash = "two"
    navigation_index(evidence)
    assert len(calls) == 2
    evidence.paths = ["app.py"]
    navigation_index(evidence)
    assert len(calls) == 3
    second = SimpleNamespace(
        **{k: v for k, v in vars(evidence).items() if k != "_navigation_index"}
    )
    navigation_index(second)
    assert len(calls) == 4


def test_packing_preserves_evidence_facts_and_original_payload():
    payload = {
        "evidence": [{"id": "a", "content": "EXACT SOURCE"}],
        "inventory": {"files": [f"module/{i}.py" for i in range(2000)]},
        "inspection": {
            "evidence": [{"id": "b", "content": "CITED BODY"}],
            "view": {"facts": [{"critical": True, "evidence_ids": ["b"]}]},
            "inventory": {"files": ["x.py"], "documents": [{"content": "CITED BODY"}]},
        },
    }
    packed = pack_repair_payload(payload)
    assert packed["evidence"] == payload["evidence"]
    assert packed["inspection"]["evidence"] == payload["inspection"]["evidence"]
    assert packed["inspection"]["view"] == payload["inspection"]["view"]
    assert len(payload["inventory"]["files"]) == 2000
    assert packed["inventory"]["navigation_omitted"] == 1970
    assert len(json.dumps(packed)) < len(json.dumps(payload))


def test_readiness_distinguishes_unsupported_forbidden_and_writable(tmp_path):
    (tmp_path / "test").mkdir()
    for name in ["app.py", "template.html", "test/test_app.py"]:
        (tmp_path / name).write_text("x=1")
    assert target_readiness(tmp_path, ["app.py"])["status"] == "eligible"
    assert (
        target_readiness(tmp_path, ["template.html"])["status"] == "unsupported_target"
    )
    assert (
        target_readiness(tmp_path, ["test/test_app.py"])["status"] == "forbidden_target"
    )
    assert target_readiness(tmp_path, ["../outside.py"])["status"] == "forbidden_target"


def test_partial_source_alias_requires_actual_full_range_and_keeps_bodies():
    rows = [
        {
            "id": "a",
            "kind": "code",
            "reference": {"file": "app.py", "start_line": 1, "end_line": 3},
            "content": "x=1\ny=2\nz=3",
        }
    ]
    payload = {
        "allowed_files": {"app.py": "x=1\ny=2"},
        "file_views": {
            "app.py": {
                "complete": False,
                "segments": [{"start_line": 1, "end_line": 2}],
            }
        },
        "inspection": {"evidence": rows},
    }
    packed = pack_repair_payload(payload)
    assert packed["inspection"]["evidence"] == rows
    assert "inspection.evidence IDs a" in packed["allowed_files"]["app.py"]
    payload["file_views"]["app.py"]["segments"][0]["end_line"] = 4
    assert pack_repair_payload(payload)["allowed_files"] == payload["allowed_files"]


def test_monitor_reads_window_progress_separately_from_controller_heartbeat(tmp_path):
    from uuid import uuid4

    from scripts.benchmarks.mechanical_monitor import observe_work

    stage = str(uuid4())
    marker = tmp_path / "test/e2e/system/case-001/scout.started.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({"stage_id": stage}))
    path = tmp_path / "artifacts/runs" / stage / "scout-progress.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"status": "running", "completed_windows": 4, "calls": 6})
    )
    work = observe_work(tmp_path / "test", tmp_path / "artifacts")
    assert work["completed_windows"] == 4
    assert work["calls"] == 6
    assert work["attention"] is None


def test_oversized_payload_has_field_receipt_without_dispatch(tmp_path):
    import pytest
    from app.domain.audit import AuditError
    from app.services.context_materials import frozen_call
    from pydantic import BaseModel

    class Output(BaseModel):
        value: str

    (tmp_path / "semantic-policy.json").write_text(
        json.dumps({"context_chars": 100, "tool_limit": 2, "repair_attempts": 1})
    )
    provider = SimpleNamespace(
        generate=lambda *args: pytest.fail("oversized payload was dispatched")
    )
    with pytest.raises(AuditError, match="上下文"):
        frozen_call(
            provider,
            "repair",
            {"phase": "inspect_semantics", "evidence": "x" * 200},
            Output,
            tmp_path / "call",
        )
    receipt = json.loads((tmp_path / "call/payload-metrics.json").read_text())
    assert receipt["status"] == "rejected_context"
    assert receipt["fields"]["evidence"] == 202
    assert not (tmp_path / "call/input.json").exists()
