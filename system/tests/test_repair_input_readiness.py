"""Repair readiness must identify unsupported targets and read actual code."""

from types import SimpleNamespace

import pytest
from app.domain.audit import AuditError
from app.services.repair_inputs import ensure_target_bodies, select_paths
from app.services.repair_semantics import SemanticRepair

from tests.test_semantic_development import InspectModel, ready, repair_service


@pytest.mark.parametrize("name", [".travis.yml", "tests_website/index.html"])
def test_configuration_and_template_only_targets_fail_before_model(name):
    with pytest.raises(AuditError) as failure:
        select_paths(SimpleNamespace(allowed_paths=[name]), [], [])
    assert failure.value.code == "unsupported_repair_target"


def test_unrelated_code_evidence_cannot_omit_actual_target_body():
    observed = []

    def read(name, start, end):
        observed.append((name, start, end))
        return {"kind": "code", "reference": {"file": name}, "content": "actual target"}

    materials = [{"kind": "code", "reference": {"file": "helper.py"}}]
    targets = [SimpleNamespace(location={"file": "app.py", "line": 40})]
    result = ensure_target_bodies(
        SimpleNamespace(read=read), targets, materials, ["app.py"]
    )
    assert observed == [("app.py", 25, 75)]
    assert result[-1]["content"] == "actual target"
    assert materials == [{"kind": "code", "reference": {"file": "helper.py"}}]
    assert (
        ensure_target_bodies(SimpleNamespace(read=read), targets, result, ["app.py"])
        == result
    )
    assert len(observed) == 1


def test_repair_reuses_supplied_source_window_without_spending_tool_budget(
    pipeline_context,
):
    def respond(payload):
        if not payload["tool_trace"]:
            return {
                "action": "tool",
                "tool": {
                    "name": "read_source",
                    "arguments": {
                        "file": "app.py",
                        "start_line": 1,
                        "end_line": 1,
                    },
                    "reason": "Read the exact target operation",
                },
            }
        assert payload["tool_trace"][-1]["reused"]
        return ready(payload)

    model = InspectModel(respond)
    service = repair_service(pipeline_context, model)
    repair = SemanticRepair(service)
    source = service.evidence.read("app.py", 1, 1)
    result = repair.reader.inspect([{"description": "eval risk"}], [source])
    assert result["view"]["facts"][0]["evidence_ids"] == [source["id"]]
    assert model.usage["calls"] == 2
    assert not (service.directory / "semantics/tools.json").exists()


def test_read_ranges_remain_writable_without_granting_unread_gaps(tmp_path):
    from app.contracts.stages import ProposedChange
    from app.services.repair_inputs import patch_context, verify_visible_changes

    lines = [
        f"value_{i} = {i}  # realistic large module source padding\n"
        for i in range(1, 501)
    ]
    text = "".join(lines)
    (tmp_path / "app.py").write_text(text)
    materials = [
        {
            "kind": "code",
            "reference": {"file": "app.py", "start_line": a, "end_line": b},
        }
        for a, b in [(1, 151), (152, 250), (300, 450)]
    ]
    _, views = patch_context(SimpleNamespace(root=tmp_path), ["app.py"], materials)
    change = ProposedChange(
        file="app.py",
        old_text="".join(lines[340:360]),
        new_text="value_341 = 0\n",
        reason="Repair an actually read target body",
    )
    verify_visible_changes([change], views)
    assert [(s["start_line"], s["end_line"]) for s in views["app.py"]["segments"]] == [
        (1, 250),
        (300, 450),
    ]
    for forbidden in [
        change.model_copy(update={"old_text": lines[274]}),
        change.model_copy(update={"file": "other.py"}),
    ]:
        with pytest.raises(AuditError, match="已提供"):
            verify_visible_changes([forbidden], views)
    assert (tmp_path / "app.py").read_text() == text


def test_small_file_does_not_grant_unread_lines(tmp_path):
    from app.services.repair_inputs import patch_context

    (tmp_path / "app.py").write_text("a=1\nb=2\nc=3\n")
    _, views = patch_context(
        SimpleNamespace(root=tmp_path),
        ["app.py"],
        [
            {
                "kind": "code",
                "reference": {"file": "app.py", "start_line": 2, "end_line": 2},
            }
        ],
    )
    assert not views["app.py"]["complete"]
    assert views["app.py"]["segments"] == [
        {"start_line": 2, "end_line": 2, "content": "b=2\n"}
    ]


def test_adjacent_pages_form_full_original_writable_body(tmp_path):
    from app.services.repair_inputs import patch_context

    text = "".join(f"line_{i} = {i}  # long source body padding\n" for i in range(500))
    (tmp_path / "app.py").write_text(text)
    materials = [
        {
            "kind": "code",
            "reference": {"file": "app.py", "start_line": a, "end_line": b},
        }
        for a, b in [(1, 151), (152, 302), (303, 453), (454, 500)]
    ]
    contents, views = patch_context(
        SimpleNamespace(root=tmp_path), ["app.py"], materials
    )
    assert views["app.py"]["complete"]
    assert contents["app.py"] == text
