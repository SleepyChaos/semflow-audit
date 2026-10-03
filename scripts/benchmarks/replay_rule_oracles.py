"""Discard invalid BQRS-reused evaluations, keep generations, replay with --rerun."""

import argparse
import hashlib
import json
import time
from pathlib import Path

from app.adapters.codeql.custom import prepare_query, fixed_dependencies
from app.adapters.codeql.rule_spec import detector_template
from scripts.benchmarks.rule_ablation_oracles import evaluate, variant_dataset


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    deadline = time.monotonic() + 1200
    while not (output / "report.json").exists():
        if time.monotonic() > deadline:
            raise TimeoutError("Generation/evaluation report not complete")
        time.sleep(5)
    report = json.loads((output / "report.json").read_text())
    prior = output / "pre-cache-fix-report.json"
    if not prior.exists():
        prior.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    cache = {}
    baseline = []
    cases = {
        entry["id"]: variant_dataset(entry["id"])
        for entry in report["manifest"]["cases"]
    }

    def key_for(query, modules, dependencies, data):
        return hashlib.sha256(
            json.dumps(
                {
                    "query": query,
                    "modules": modules,
                    "dependencies": dependencies,
                    "dataset_hash": data["hash"],
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()

    for identifier, data in cases.items():
        query, provenance = detector_template(data["language"], data["operation"])
        dependencies = fixed_dependencies(data["language"])
        pack = output / "replay-baseline" / identifier
        prepare_query(pack, data["language"], query, {}, dependencies)
        start = time.perf_counter()
        result = evaluate(output / "holdouts" / identifier, pack, data, pack / "oracle")
        key = key_for(query, {}, dependencies, data)
        cache[key] = result
        baseline.append(
            {
                "case": identifier,
                "result": result,
                "provenance": provenance,
                "evaluation_seconds": time.perf_counter() - start,
            }
        )
        print("BASELINE", identifier, result["status"], flush=True)
    rows = [
        json.loads(path.read_text()) for path in (output / "records").glob("*.json")
    ]
    for row in rows:
        row.pop("oracle_error", None)
        if not row["rules"]:
            row["oracle"] = {"status": "not_generated"}
        else:
            rule = row["rules"][0]
            data = cases[row["case"]]
            key = key_for(rule["query"], rule["modules"], rule["dependencies"], data)
            start = time.perf_counter()
            try:
                if key not in cache:
                    pack = output / "replay-evaluation" / row["stage"]["id"]
                    prepare_query(
                        pack,
                        rule["language"],
                        rule["query"],
                        rule["modules"],
                        rule["dependencies"],
                    )
                    cache[key] = evaluate(
                        output / "holdouts" / row["case"], pack, data, pack / "oracle"
                    )
                    row["evaluation_cache_hit"] = False
                else:
                    row["evaluation_cache_hit"] = True
                row["oracle"] = cache[key]
                row["evaluation_cache_key"] = key
            except Exception as exc:
                row["oracle"] = {"status": "execution_error"}
                row["oracle_error"] = {"type": type(exc).__name__, "message": str(exc)}
            row["evaluation_seconds"] = time.perf_counter() - start
        row["evaluator_version"] = 3
        (output / "records" / f"{row['stage']['id']}.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=2)
        )
        print("REPLAY", row["arm"], row["case"], row["oracle"]["status"], flush=True)
    report["records"] = rows
    report["baseline"] = baseline
    report["evaluator_version"] = 3
    report["manifest"] = json.loads((output / "manifest.json").read_text())
    report["evaluation_errata"] = (
        "Prior dynamic query evaluations could reuse BQRS by identical pack/query identity. Discarded and replayed with --rerun. Original candidates and model calls unchanged."
    )
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    print("REPORT=" + str(output / "report.json"), flush=True)


if __name__ == "__main__":
    main()
