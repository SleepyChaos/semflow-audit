"""Evidence/path and unresolved-output checks for the RealVuln experiment adapter."""

import json
from pathlib import Path

import pytest
from scripts.benchmarks.realvuln_score import cwes, metrics, normalized, project_outputs

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def official(monkeypatch):
    path = ROOT / ".local-workspace/realvuln-v1-original"
    if not (path / "scorer/matcher.py").exists():
        pytest.skip("Requires acquired official RealVuln v1 evaluator")
    monkeypatch.syspath_prepend(str(path))
    from scorer.matcher import match_findings

    return match_findings


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def test_codeql_cwe_normalization_keeps_unknown():
    assert cwes(["external/cwe/cwe-079", "external/cwe/cwe-89", "CWE-089"]) == [
        "CWE-79",
        "CWE-89",
    ]
    assert cwes(["security"]) == ["unknown"]


def test_official_matcher_counts_duplicates_traps_and_wrong_locations(
    official, tmp_path
):
    gold = {
        "findings": [
            {
                "id": "positive",
                "file": "app.py",
                "acceptable_cwes": ["CWE-89"],
                "is_vulnerable": True,
                "location": {"start_line": 30, "end_line": 30},
            },
            {
                "id": "trap",
                "file": "app.py",
                "acceptable_cwes": ["CWE-79"],
                "is_vulnerable": False,
                "location": {"start_line": 60, "end_line": 60},
            },
        ]
    }
    findings = []
    for index, (line, weakness) in enumerate(
        ((30, "CWE-89"), (30, "CWE-89"), (60, "CWE-79"), (120, "CWE-89"))
    ):
        findings += normalized(
            {"file": "app.py", "line": line},
            [weakness],
            str(index),
            "finding",
            "test",
            tmp_path,
        )
    assert [r.classification for r in official(findings, gold)] == [
        "TP",
        "FP",
        "FP",
        "FP",
    ]
    wrong_cwe = normalized(
        {"file": "app.py", "line": 30}, ["unknown"], "u", "finding", "test", tmp_path
    )
    assert [r.classification for r in official(wrong_cwe, gold)] == ["FP", "FN", "TN"]


def test_location_does_not_strip_arbitrary_project_prefix(official, tmp_path):
    inside = normalized(
        {"file": str(tmp_path / "app.py"), "line": 5},
        ["CWE-89"],
        "a",
        "finding",
        "test",
        tmp_path,
    )
    assert inside[0].file == "app.py"
    with pytest.raises(ValueError, match="outside"):
        normalized(
            {"file": str(tmp_path.parent / "other/app.py"), "line": 5},
            ["CWE-89"],
            "b",
            "finding",
            "test",
            tmp_path,
        )


def test_model_cwe_leading_zero_matches_same_vulnerability(official, tmp_path):
    findings = normalized(
        {"file": "app.py", "line": 53},
        ["CWE-079"], "model", "XSS", "test", tmp_path,
    )
    gold = {"findings": [{
        "id": "xss", "file": "app.py", "acceptable_cwes": ["CWE-79"],
        "is_vulnerable": True, "location": {"start_line": 53},
    }]}
    assert findings[0].cwe == "CWE-79"
    assert official(findings, gold)[0].classification == "TP"


def test_pending_and_unreviewed_remain_in_retained_arm(official, tmp_path):
    project = "synthetic-project"
    findings = [
        {
            "id": name,
            "locations": [{"file": "app.py", "line": line}],
            "tags": ["external/cwe/cwe-89"],
            "message": name,
        }
        for name, line in (("pending", 10), ("excluded", 20), ("unreviewed", 30))
    ]
    put(
        tmp_path / "static" / project / "result.json",
        {"status": "succeeded", "rounds": [{"findings": findings}]},
    )
    candidates = [
        {
            "id": name,
            "static_finding_id": name,
            "related_target": None,
            "model_assessment": assessment,
            "location": {"file": "app.py", "line": line},
            "weakness": "unknown",
            "description": name,
        }
        for name, line, assessment in (
            ("pending", 10, "pending"),
            ("excluded", 20, "excluded"),
        )
    ]
    put(tmp_path / "system" / project / "review.json", {"candidates": candidates})
    outputs, status = project_outputs(tmp_path, project, tmp_path / "source")
    assert outputs["system_supported"] == []
    assert [f.finding_id for f in outputs["system_retained"]] == [
        "pending",
        "unreviewed",
    ]
    assert status["unresolved_candidates"] == 1
    assert status["system_status"] == "not_finished"


def test_strict_micro_keeps_failed_project_denominator():
    completed = {"tp": 3, "fp": 1, "fn": 2, "tn": 0}
    failed = {"tp": 0, "fp": 0, "fn": 5, "tn": 1}
    result = metrics([completed, failed])
    assert result["recall"] == 0.3
    assert result["precision"] == 0.75
    assert result["f3"] == pytest.approx(30 / 94)
