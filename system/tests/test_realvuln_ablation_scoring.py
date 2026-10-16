"""Preserve official allocation while exposing ambiguous multi-label evidence."""

from pathlib import Path

import pytest
from scripts.benchmarks.realvuln_ablation_io import Evaluator, findings
from scripts.benchmarks.realvuln_ablation_transitions import transitions


def test_candidate_has_multiple_compatible_labels_but_only_one_allocated():
    root = (
        Path(__file__).resolve().parents[2]
        / "artifacts/research/realvuln/20261013-progress-v2"
    )
    if not (root / "evaluator-only/scorer/matcher.py").exists():
        pytest.skip("Frozen external benchmark evaluator is not installed")
    evaluator = Evaluator(root)
    gold = {
        "repo_id": "synthetic",
        "findings": [
            {
                "id": identifier,
                "file": "app.py",
                "acceptable_cwes": ["CWE-95"],
                "location": {"start_line": line},
                "is_vulnerable": True,
                "cwe": "CWE-95",
                "severity": "high",
            }
            for identifier, line in (("label-a", 10), ("label-b", 11))
        ],
    }
    candidate = {
        "id": "one-source-candidate",
        "location": {"file": "app.py", "line": 10},
        "weaknesses": ["CWE-95"],
        "description": "Actual input reaches eval",
    }
    _, matched_ids, allocation, compatible = evaluator.score(
        "synthetic", "B", findings([candidate], "B", Path("/tmp")), gold
    )
    assert matched_ids == {"label-a"}
    assert allocation == {"one-source-candidate": ["label-a"]}
    assert compatible == {"one-source-candidate": ["label-a", "label-b"]}


def test_static_unknown_cwe_transition_retains_actual_scoring_fallback():
    root = (
        Path(__file__).resolve().parents[2]
        / "artifacts/research/realvuln/20261013-progress-v2"
    )
    if not (root / "evaluator-only/scorer/matcher.py").exists():
        pytest.skip("Frozen external benchmark evaluator is not installed")
    evaluator = Evaluator(root)
    gold = {
        "repo_id": "synthetic",
        "findings": [
            {
                "id": "eval-label",
                "file": "app.py",
                "acceptable_cwes": ["CWE-95"],
                "location": {"start_line": 10},
                "is_vulnerable": True,
                "cwe": "CWE-95",
                "severity": "high",
            }
        ],
    }
    raw = [
        {
            "id": "static-alert",
            "source": "codeql",
            "location": {"file": "app.py", "line": 10},
            "weaknesses": ["CWE-95", "CWE-79"],
            "description": "Input reaches eval",
        }
    ]
    candidate = {
        "id": "reviewed-alert",
        "static_finding_id": "static-alert",
        "identity_key": "static:static-alert",
        "weakness": "unknown",
        "model_assessment": "supported",
        "location": raw[0]["location"],
        "description": "Input reaches eval",
        "evidence_ids": ["source-evidence"],
    }
    before = evaluator.score("synthetic", "A", findings(raw, "A", Path("/tmp")), gold)
    after = evaluator.score(
        "synthetic",
        "D",
        findings(
            [{**candidate, "weaknesses": raw[0]["weaknesses"]}], "D", Path("/tmp")
        ),
        gold,
    )
    review = {"candidates": [candidate], "stage": {"result": {"batches": []}}}
    rows = transitions(
        "synthetic",
        root,
        raw,
        review,
        {"C": before, "F": after},
        evaluator,
        gold,
        Path("/tmp"),
    )
    assert after[0]["tp"] == 1
    assert rows[0]["after_supported_allocated_gold_ids"] == ["eval-label"]
    assert rows[0]["after_compatible_gold_ids"] == ["eval-label"]
    assert rows[0]["after_scored_cwes"] == ["CWE-95", "CWE-79"]
