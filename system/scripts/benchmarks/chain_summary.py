"""Summarize saved attempts without contacting services or inventing completions."""

import argparse
import json
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree


def summarize(base):
    stages, audits, attempts = {}, {}, []
    for directory in sorted(base.glob("20261009-v*")):
        report_path = directory / "report.json"
        if not report_path.exists():
            continue
        report = json.loads(report_path.read_text())
        attempts.append(
            {
                "id": directory.name,
                "counts": dict(Counter(s["status"] for s in report["steps"])),
                "steps": [
                    {
                        k: s[k]
                        for k in ("language", "name", "status", "error", "reason")
                        if k in s
                    }
                    for s in report["steps"]
                ],
                "scope": report["scope"],
            }
        )
        for path in directory.glob("*-stage-receipt.json"):
            stage = json.loads(path.read_text())
            stages[stage["id"]] = stage
        for path in directory.glob("*-audit-receipt.json"):
            audit = json.loads(path.read_text())
            audits[audit["id"]] = audit
    regression = ElementTree.parse(base / "20261009-v1/regression/junit.xml")
    tests = list(regression.iter("testcase"))
    cases = []
    calibration = base / "20261009-v2/calibration/summary.json"
    if calibration.exists():
        cases = json.loads(calibration.read_text())["cases"]
    calls = [call for stage in stages.values() for call in stage.get("model_calls", [])]
    usage = {
        "calls": len(calls),
        "input_tokens": sum(c.get("input_tokens") or 0 for c in calls),
        "output_tokens": sum(c.get("output_tokens") or 0 for c in calls),
        "missing_token_receipts": sum(
            c.get("input_tokens") is None or c.get("output_tokens") is None
            for c in calls
        ),
        "response_models": dict(Counter(c.get("response_model") for c in calls)),
        "money": "invoice_not_obtained",
    }
    return {
        "campaign": "20261009-chain-completion",
        "status": "partial_execution_blocked_by_approval_service_quota",
        "all_product_chains_completed": False,
        "regression": {
            "testcases": len(tests),
            "failures": sum(t.find("failure") is not None for t in tests),
            "errors": sum(t.find("error") is not None for t in tests),
            "skipped": sum(t.find("skipped") is not None for t in tests),
            "real_tools_enabled": True,
            "models": "controlled_test_doubles_not_accuracy_evaluation",
        },
        "attempts": attempts,
        "audits": [
            {
                "id": a["id"],
                "language": a["language"],
                "status": a["status"],
                "snapshot_hash": a["snapshot_hash"],
                "findings": len(a["findings"]),
            }
            for a in audits.values()
        ],
        "stage_counts": dict(
            Counter(s["kind"] + ":" + s["status"] for s in stages.values())
        ),
        "stages": [
            {
                k: s[k]
                for k in ("id", "audit_id", "kind", "status", "prompt_version", "usage")
            }
            for s in stages.values()
        ],
        "calibration": {
            "cases": cases,
            "admitted": sum(c["admitted"] for c in cases),
            "before_v1": False,
            "before_v2": True,
        },
        "usage": usage,
        "not_evaluated": [
            "browser-confirmation",
            "real-worker-repair-and-acceptance",
            "new-rule-generation-approval-holdout-publication-reuse",
            "new-knowledge-import-index-retrieval",
            "final-browser-report-isolation-retirement",
        ],
        "independent_human_review": False,
        "target_http_exploit_replay": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.base)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "regression": result["regression"],
                "stage_counts": result["stage_counts"],
                "usage": result["usage"],
            },
            ensure_ascii=False,
        )
    )
