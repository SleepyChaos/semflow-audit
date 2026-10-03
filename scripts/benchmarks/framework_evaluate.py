"""Replay framework evaluator from stored candidates, without additional AI calls."""

import argparse
import json
from pathlib import Path

from app.adapters.codeql.custom import compile_query, prepare_query, fixed_dependencies
from app.adapters.codeql.rule_spec import detector_template
from scripts.benchmarks.framework_ablation import fixture
from scripts.benchmarks.rule_ablation_oracles import build_databases, evaluate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output
    report = json.loads((output / "report.json").read_text())
    baseline = []
    old_manifest = json.loads((output / "manifest.json").read_text())
    # A literal expected line 7 in the initial fixture builder was invalid.
    # Generation had already finished; no independent labels entered prompts.
    (output / "evaluator-errata.json").write_text(
        json.dumps(
            {
                "reason": "Expected line 7 exceeded the six-line fixture. Correct to actual marked sink line 6 before evaluation. No model regeneration or changed code contents.",
                "prior_dataset_metadata": old_manifest["cases"],
                "evaluator_version": 2,
            },
            indent=2,
        )
    )
    for index in range(3):
        case, _ = fixture(index)
        directory = output / "holdouts" / case["id"]
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "dataset.json").write_text(json.dumps(case, indent=2))
        if not (directory / "negative-database").exists():
            build_databases(directory, case)
        pack = directory / "baseline"
        query, provenance = detector_template("python", "eval")
        prepare_query(pack, "python", query, {}, fixed_dependencies("python"))
        compile_query(pack, pack / "compile.log")
        baseline.append(
            {
                "case": case["id"],
                "oracle": evaluate(directory, pack, case, pack / "oracle"),
                "provenance": provenance,
            }
        )
        for row in report["records"]:
            if row["case"] != case["id"]:
                continue
            if not row["rules"]:
                row["oracle"] = {"status": "not_generated"}
                continue
            rule = row["rules"][0]
            pack = output / "evaluation" / row["stage"]["id"]
            prepare_query(
                pack, "python", rule["query"], rule["modules"], rule["dependencies"]
            )
            try:
                row["oracle"] = evaluate(directory, pack, case, pack / "oracle")
            except Exception as exc:
                row["oracle_error"] = {"message": str(exc), "type": type(exc).__name__}
            print(
                row["arm"],
                row["case"],
                row.get("oracle", {}).get("status", "error"),
                flush=True,
            )
        report["baseline"] = baseline
        (output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2)
        )


if __name__ == "__main__":
    main()
