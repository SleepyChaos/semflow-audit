"""Aggregate frozen supplemental receipts without running or tuning models."""

import argparse
import json
import tarfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from scripts.benchmarks.formal_scoring import score_cases
from scripts.benchmarks.supplemental_prepare import ROOT, save, sha


def read(path):
    return json.loads(path.read_text())


def compact(score):
    return {
        k: score[k]
        for k in ("counts", "precision", "recall", "f1", "false_positive_rate")
    }


def aggregate_counts(scores):
    counts = Counter()
    for score in scores:
        counts.update(score["counts"])
    tp, fp, tn, fn = (counts[key] for key in ("TP", "FP", "TN", "FN"))
    return {
        "counts": dict(counts),
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        "false_positive_rate": fp / (fp + tn) if fp + tn else None,
    }


def discovery(directory):
    protocol = read(directory / "protocol.json")
    records, stage_receipts = [], []
    selected_files = []
    for sample in ("validation-01", "validation-02"):
        material = directory / "samples" / sample
        selection = read(material / "evaluator-selection.json")
        files = {r["file"] for r in selection["selected"]}
        selected_files.append(files)
        assert len(files) == 48
        assert sum(r["vulnerable"] for r in selection["selected"]) == 24
        assert all(
            sha(material / "source" / p) == h
            for p, h in selection["source_hashes"].items()
        )
        run = directory / "runs/revision-01" / sample
        assert read(run / "integrity.json")["input_and_implementation_unchanged"]
        result = read(run / "evaluation.json")
        bandit = read(directory / "comparators/bandit" / sample / "result.json")
        bandit_records = []
        for record in bandit["records"]:
            raw = (
                directory
                / "comparators/bandit"
                / sample
                / f"round-{record['repetition']}.json"
            )
            parsed = read(raw)
            assert isinstance(parsed.get("results"), list) and not parsed.get("errors")
            assert record["status"] == "succeeded"
            bandit_records.append(
                score_cases(selection["selected"], record["findings"])
            )
        assert all(s["counts"] == bandit_records[0]["counts"] for s in bandit_records)
        scores = {k: compact(v) for k, v in result["scores"].items()}
        scores["Bandit"] = compact(bandit_records[0])
        tasks = Counter()
        for row in result["coverage"]:
            tasks.update(row["tasks"])
        paths = [p for p in run.glob("*/scout.json")] + [
            p for p in run.glob("*/review.json")
        ]
        assert len(paths) == 24
        stage_receipts += [read(p)["stage"] for p in paths]
        records.append(
            {
                "sample": sample,
                "cases": 48,
                "positive": 24,
                "negative": 24,
                "categories": selection["distribution"],
                "scores": scores,
                "unreviewed_candidates": result["unreviewed"],
                "alternate_CWE_not_adjudicated": len(
                    result["alternate_CWE_not_auto_adjudicated"]
                ),
                "outside_target_supported_alerts": len(
                    result["scores"]["Platform_supported"]["outside_target_alerts"]
                ),
                "incomplete_case_windows": sum(
                    r["windows"] != r["inspected"] for r in result["coverage"]
                ),
                "safety_task_conclusions": dict(tasks),
                "parallel_wall_seconds": result["parallel_wall_seconds"],
                "usage": result["usage"],
                "structural_prior_overlap_cases": selection[
                    "structural_prior_overlap_cases"
                ],
            }
        )
    assert not selected_files[0] & selected_files[1]
    for previous in protocol["historical_exclusions"]:
        old = {r["file"] for r in read(ROOT / previous)["selected"]}
        assert not old & (selected_files[0] | selected_files[1])
    relevant = {
        p: h
        for p, h in protocol["implementation_hashes"].items()
        if p.startswith(("system/backend/app/", "benchmarks/experiments/owasp48/"))
        or p
        in {
            "system/scripts/benchmarks/formal_runtime.py",
            "system/scripts/benchmarks/formal_baseline.py",
            "system/scripts/benchmarks/formal_scoring.py",
        }
    }
    assert all(sha(ROOT / p) == h for p, h in relevant.items())
    save(
        directory / "integrity.json",
        {
            "case_hashes_unchanged": True,
            "case_disjoint_from_prior": True,
            "case_disjoint_between_samples": True,
            "execution_relevant_hashes_unchanged": True,
            "unrelated_new_helpers_not_claimed_frozen": [
                p
                for p, h in protocol["implementation_hashes"].items()
                if sha(ROOT / p) != h
            ],
            "shape_screening_is_not_semantic_or_training_novelty_proof": True,
        },
    )
    return {
        "records": records,
        "combined": {
            name: aggregate_counts([r["scores"][name] for r in records])
            for name in records[0]["scores"]
        },
        "cases": 96,
        "all_alert_human_precision": None,
        "official_scorecard": False,
        "training_unseen_claim": False,
    }, stage_receipts


def repair(directory):
    rows = read(directory / "report.json")["records"]
    assert len(rows) == 20 and len({r["task_id"] for r in rows}) == 10
    assert read(directory / "integrity.json")["production_unchanged"]
    groups = {}
    for version in ("1", "2"):
        part = [r for r in rows if r["version"] == version]
        groups[version] = {
            "requests": len(part),
            "completed": sum(r["status"] == "completed" for r in part),
            "failed": sum(r["status"] == "failed" for r in part),
            "hidden_joint_pass": sum(r["oracle"]["joint_pass"] for r in part),
            "end_to_end_pass": sum(r["end_to_end_pass"] for r in part),
            "not_evaluated": sum(
                r["oracle"]["status"] == "not_evaluated" for r in part
            ),
            "languages": {
                lang: {
                    "requests": sum(r["language"] == lang for r in part),
                    "end_to_end_pass": sum(
                        r["end_to_end_pass"] and r["language"] == lang for r in part
                    ),
                }
                for lang in ("python", "javascript")
            },
        }
    stages = [read(p)["stage"] for p in directory.glob("runs/*/v*/generation.json")]
    return {
        "tasks": 10,
        "requests": 20,
        "calibrated": read(directory / "calibration/summary.json")["admitted"],
        "groups": groups,
        "failures": [
            {
                "task": r["task_id"],
                "version": r["version"],
                "status": r["status"],
                "oracle": r["oracle"]["status"],
            }
            for r in rows
            if not r["end_to_end_pass"]
        ],
        "derived_unreviewed": True,
        "natural_CVE_or_service_PoC": False,
    }, stages


def rules(directory):
    rows = read(directory / "report.json")["records"]
    assert len(rows) == 18
    assert read(directory / "integrity.json")["rules_unchanged"]
    groups = {}
    for family in sorted({r["family"] for r in rows}):
        part = [r for r in rows if r["family"] == family]
        groups[family] = {
            "historical_candidates": len(part),
            "passed": sum(r["oracle"]["status"] == "passed" for r in part),
            "errors": sum(r["oracle"]["status"] == "error" for r in part),
            **{k: sum(r["oracle"].get(k, 0) for r in part) for k in ("tp", "fp", "fn")},
        }
    return {
        "historical_candidates": 18,
        "new_generation_requests": 0,
        "families": 6,
        "new_source_files": 12,
        "positive_sinks": 12,
        "safe_handlers": 12,
        "passed": sum(r["oracle"]["status"] == "passed" for r in rows),
        "failed": sum(r["oracle"]["status"] == "failed" for r in rows),
        "errors": sum(r["oracle"]["status"] == "error" for r in rows),
        "groups": groups,
        "derived_unreviewed": True,
        "purpose": "vulnerability_detector historical arm; current review_anchor not assessed",
        "RAG_causal_gain": None,
        "new_model_calls": 0,
    }


def usage(stages):
    counters = Counter()
    models = set()
    calls = []
    for stage in stages:
        for k in ("calls", "input_tokens", "output_tokens"):
            counters[k] += stage["usage"].get(k, 0)
        calls += stage.get("model_calls", [])
    for call in calls:
        if call.get("response_model"):
            models.add(call["response_model"])
    return {
        "stages": len(stages),
        **dict(counters),
        "response_models": sorted(models),
        "model_call_receipts": len(calls),
        "missing_token_receipts": sum(
            c.get("input_tokens") is None or c.get("output_tokens") is None
            for c in calls
        ),
        "billed_currency_cost": None,
        "performance_comparison": "Concurrent discovery cohorts, repair and CodeQL probes overlap; these are workload receipts, not fair latency rankings",
    }


def freeze_inputs(output):
    for name, includes in (
        ("discovery", ["samples"]),
        ("repair", ["sources", "evaluator-only"]),
        ("rules", ["holdouts", "frozen-rules.json", "hidden-manifest.json"]),
    ):
        directory = output / name
        destination = directory / "input-source.tar.gz"
        if destination.exists():
            continue
        with tarfile.open(destination, "w:gz") as bundle:
            for include in includes:
                root = directory / include
                paths = root.rglob("*") if root.is_dir() else [root]
                for p in sorted(paths):
                    if (
                        p.is_file()
                        and not p.is_symlink()
                        and not any(
                            x in p.parts
                            for x in (
                                "__pycache__",
                                "positive-database",
                                "negative-database",
                            )
                        )
                    ):
                        if name == "rules" and p.suffix not in {".json", ".py", ".js"}:
                            continue
                        bundle.add(p, arcname=p.relative_to(directory), recursive=False)
        save(
            directory / "input-freeze-receipt.json",
            {
                "archive": destination.relative_to(ROOT).as_posix(),
                "sha256": sha(destination),
                "synthetic_or_public_inputs_only": True,
                "evaluator_answers_private": True,
            },
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    d, ds = discovery(output / "discovery")
    r, rs = repair(output / "repair")
    g = rules(output / "rules")
    gui = read(output / "gui-validated/report.json")
    junit = ET.parse(output / "reliability/junit.xml").getroot()
    nodes = list(junit.iter("testcase"))
    assert (
        len(nodes) == 33
        and not list(junit.iter("failure"))
        and not list(junit.iter("error"))
    )
    assert "OK" in (output / "reliability/archive-runner-tests.log").read_text()
    result = {
        "campaign_id": "20261009-supplemental-v1",
        "archive_next": "20261009-workspace-v2",
        "production_changes": False,
        "discovery": d,
        "repair": r,
        "rules": g,
        "gui": {
            k: gui[k]
            for k in (
                "passed",
                "failed",
                "checks",
                "browser_version",
                "browser_channel",
                "scope",
            )
        },
        "reliability": {
            "pytest_passed": 33,
            "new_data_runner_tests_passed": 5,
            "archive_tests_rechecked": 9,
            "distinct_tests": 38,
            "junit_sha256": sha(output / "reliability/junit.xml"),
        },
        "usage": usage(ds + rs),
        "remaining_gaps": [
            "Cross-framework/cross-language independent discovery repositories",
            "Double-blind human adjudication of all alerts and roots",
            "Human-admitted natural repair tasks and service PoC replay",
            "New rule generation on independent CWE/framework tasks and current review-anchor purpose",
            "Matched RAG retrieval/reranker ablation with budgets",
            "GUI real upload/Worker/model/confirmation/repair/publication/report completion",
            "Provider invoice cost and matched performance experiments",
        ],
    }
    freeze_inputs(output)
    save(output / "summary.json", result)
    save(ROOT / "benchmarks/reports/supplemental-20261009-summary.json", result)
    print(
        json.dumps(
            {
                "discovery": d["combined"],
                "repair": r["groups"],
                "rules": {k: g[k] for k in ("passed", "failed", "errors")},
                "gui": {k: gui[k] for k in ("passed", "failed")},
                "usage": result["usage"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
