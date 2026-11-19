"""Regression tests for bounded source coverage and review scheduling."""

import hashlib
import json
from types import SimpleNamespace

from semflow_research.adapters.project_map import build_project_map
from semflow_research.adapters.project_navigation import navigation_index
from semflow_research.discovery.review_pool import batches


from uuid import uuid4

import pytest
from discovery_cases import settings as settings
from openai.types.chat import ChatCompletion
from semflow_contracts.runs import validate_spec
from semflow_research.public.discovery import execute
from semflow_research.public.discovery_results import read_result
from semflow_research.public.runtime import prepare
from semflow_research.runtime.sources import capture


def evidence_at(root):
    return SimpleNamespace(
        root=root,
        files=lambda: iter(sorted(root.rglob("*.py"))),
        allowed=lambda name: root / name,
        source_context=SimpleNamespace(snapshot_hash="snapshot", language="python"),
    )


def test_risk_selection_prioritizes_a_sensitive_call_in_a_late_module(tmp_path):
    for index in range(12):
        (tmp_path / f"a{index:02}.py").write_text("def helper():\n    return 1\n")
    (tmp_path / "z_worker.py").write_text(
        "import subprocess\n\ndef worker(task):\n    return subprocess.run(task)\n"
    )
    project = build_project_map(
        evidence_at(tmp_path), 20, "business_semantic", risk_aware=True
    )
    first = project["units"][0]
    assert first["file"] == "z_worker.py"
    assert first["risk"]["reasons"] == ["process"]
    assert project["files"][-1]["functions"][0]["qualified_name"] == "worker"
    assert len({unit["id"] for unit in project["units"]}) == len(project["units"])


def test_declared_big5_and_unknown_encoding_are_isolated(tmp_path):
    (tmp_path / "a.py").write_text("import flask\napp = flask.Flask(__name__)\n")
    (tmp_path / "b.py").write_bytes("# coding: big5\nlabel = '中文'\n".encode("big5"))
    (tmp_path / "c.py").write_bytes(b"# no declaration\nvalue='\xff'\n")
    evidence = evidence_at(tmp_path)
    navigation = navigation_index(evidence)
    assert navigation["python_factories"] == ["a.py"]
    assert [row["file"] for row in navigation["unreadable"]] == ["c.py"]
    project = build_project_map(evidence, 20, risk_aware=True)
    assert {unit["file"] for unit in project["units"]} == {"a.py", "b.py"}
    assert project["skipped"][0]["code"] == "source_unreadable"


def test_source_balanced_review_keeps_severe_static_and_independent_scout():
    low = {
        "candidate_id": "low",
        "origin": "static",
        "location": {"file": "a.py", "line": 2},
        "static_alert": {"tags": ["security"], "security_severity": "7.5"},
    }
    severe = {
        "candidate_id": "severe",
        "origin": "static",
        "location": {"file": "z.py", "line": 41},
        "static_alert": {
            "tags": ["security"],
            "security_severity": "9.8",
            "code_flows": [[{"file": "z.py", "line": 4}]],
        },
    }
    scout = {
        "candidate_id": "scout",
        "origin": "scout",
        "evidence_ids": ["page"],
        "location": {"file": "y.py", "line": 4},
    }
    result = batches({"entries": [low, scout, severe]}, 2, source_balanced=True)
    assert [[entry["candidate_id"] for entry in batch] for batch in result] == [
        ["severe", "scout"],
        ["low"],
    ]


@pytest.mark.parametrize("valid", [True, False, "display_overflow"])
def test_scout_reports_actual_model_input_and_preserves_schema_failures(
    research_case,
    settings,  # noqa: F811 - pytest injects the imported fixture
    monkeypatch,
    valid,
):
    case = research_case
    (case.source / "a_legacy.py").write_bytes(
        "# coding: big5\nlabel = '中文'\n".encode("big5")
    )
    (case.source / "b_unreadable.py").write_bytes(b"# bad bytes\n\xff\n")
    source = capture(case.source, artifacts=case.artifacts, languages=("python",))
    ref = case.artifacts.commit(
        b"Source-only mock.", kind="prompt", schema_version="prompt/1"
    )
    raw = case.spec.model_dump(mode="json")
    raw.update(
        execution_id=str(uuid4()),
        operation="scout",
        source=source.model_dump(mode="json"),
        prompts=[
            {
                "role": "scout",
                "version": "8",
                "template_id": "scout",
                "content": ref.model_dump(mode="json"),
                "sha256": ref.sha256,
            }
        ],
        inputs={
            "window_policy": {
                "version": "2",
                "max_windows": 1,
                "max_steps_per_window": 1,
                "max_calls": 1,
            }
        },
        model={
            "provider": "scripted-test",
            "model": "scripted",
            "endpoint_profile": "mock",
            "output_schema_version": "1",
        },
    )
    raw["implementation"]["method_version"] = "8"
    raw["policy"].update(max_tokens=100000, max_context_chars=40000)
    spec = validate_spec(raw)
    context = prepare(spec, root=case.ledger.root, settings=settings)

    def reply(**kwargs):
        payload = json.loads(kwargs["messages"][-1]["content"])[
            "untrusted_analysis_material"
        ]
        body = {
            "action": "final",
            "scope_summary": "Window observed successfully.",
            "task_checks": [
                {
                    "task_id": task["id"],
                    "status": "unknown",
                    "reason": "Source scope remains incomplete."
                    * (12 if valid == "display_overflow" else 1),
                }
                for task in payload["inspection_tasks"]
            ],
        }
        return ChatCompletion(
            id="mock",
            model="scripted",
            object="chat.completion",
            created=0,
            choices=[
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(body)
                        if valid
                        else '{"action":"incorrect"}',
                    },
                }
            ],
            usage={"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        )

    monkeypatch.setattr(context.model.client.chat.completions, "create", reply)
    legacy_bytes = (case.source / "a_legacy.py").read_bytes()
    evidence = context.source.read("a_legacy.py", 2, 2)
    assert evidence.location.file_sha256 == hashlib.sha256(legacy_bytes).hexdigest()
    assert evidence.snapshot_id == spec.source.snapshot_id
    context.source.validate(evidence)
    receipt = execute(spec, context)
    assert receipt.usage.calls == 1
    assert receipt.execution_status == ("completed" if valid else "failed"), (
        receipt.failure
    )
    view = read_result(spec.execution_id, root=case.ledger.root)
    coverage = view.trace.state["coverage"]
    assert len(coverage["submitted_window_ids"]) == 1
    assert coverage["files_with_model_input"] >= 1
    assert coverage["error_counts"]["source_unreadable"] == 1
    assert coverage["inspected_windows"] == int(bool(valid))
    if valid == "display_overflow":
        call = view.trace.model_calls[0]
        assert (
            call["response_ref"]
            and call["recovery_class"] == "revalidated_display_fields"
        )
        assert coverage["inspected_windows"] == 1
    if not valid:
        assert receipt.failure.code == "model_output_invalid"
        assert receipt.completeness.status == "none"
        assert coverage["error_counts"]["schema_invalid"] == 1
        call = view.trace.model_calls[0]
        assert call["response_ref"] and call["validation_feedback"]


def test_cross_source_overlap_breaks_a_static_severity_tie():
    origin = {
        "origin": "static",
        "static_alert": {"tags": ["external/cwe/cwe-078"], "security_severity": "9.8"},
    }
    isolated = {**origin, "candidate_id": "a", "location": {"file": "a.py", "line": 6}}
    matched = {**origin, "candidate_id": "b", "location": {"file": "b.py", "line": 8}}
    independent = {
        "origin": "scout",
        "candidate_id": "c",
        "location": {"file": "b.py", "line": 9},
        "weakness": "CWE-78",
        "evidence_ids": ["page"],
    }
    result = batches(
        {"entries": [isolated, matched, independent]}, 2, source_balanced=True
    )
    assert [row["candidate_id"] for row in result[0]] == ["b", "c"]


def test_failed_call_source_is_submitted_but_not_counted_as_inspected(tmp_path):
    from semflow_research.discovery.coverage import scout_coverage

    unit = tmp_path / "units" / "one"
    a = {"file": "a.py", "start_line": 1, "end_line": 5}
    b = {"file": "b.py", "start_line": 1, "end_line": 5}
    for i, region in enumerate((a, b)):
        call = unit / f"call-{i}"
        call.mkdir(parents=True)
        (call / "source-input.json").write_text(
            json.dumps({"unit_id": "one", "ranges": [region]})
        )
    (unit / "evidence-coverage.json").write_text(json.dumps([b]))
    function = {"qualified_name": "work", "start_line": 1, "end_line": 5}
    project = {
        "files": [{"file": f, "functions": [function]} for f in ("a.py", "b.py")],
        "skipped": [],
        "units": [{"id": "one"}],
    }
    stats = scout_coverage(
        project,
        [{"unit_id": "one", "status": "inspected"}],
        project["units"],
        tmp_path,
        None,
    )
    assert stats["function_coverage"]["a.py"][0]["supplied"]
    assert not stats["function_coverage"]["a.py"][0]["inspected"]
    assert stats["function_coverage"]["b.py"][0]["whole_function"]
