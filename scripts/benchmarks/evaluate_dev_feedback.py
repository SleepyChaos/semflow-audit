"""Evaluate supplementary candidates against existing hidden databases, never prompts."""

import argparse
import hashlib
import json
from pathlib import Path

from app.adapters.codeql.custom import prepare_query
from scripts.benchmarks.rule_ablation_oracles import evaluate, variant_dataset
from scripts.benchmarks.framework_ablation import fixture


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    manifest = json.loads((output / "manifest.json").read_text())
    main_root, framework_root = [Path(path) for path in manifest["references"]]
    report = json.loads((output / "report.json").read_text())
    cache = {}
    for row in report["records"]:
        if not row["rules"]:
            row["oracle"] = {"status": "not_generated"}
            row["dev_oracle"] = {"status": "not_generated"}
        else:
            rule = row["rules"][0]
            development = rule["validation"].get("development", {})
            row["dev_oracle"] = {
                "status": development.get("status", "not_evaluated"),
                "meaning": "Actual dev execution inside bounded generation loop",
            }
            if row["arm"].startswith("K_"):
                data = variant_dataset(row["case"])
                root = main_root
            else:
                data, _ = fixture(int(row["case"].rsplit("-", 1)[-1]))
                root = framework_root
            key = hashlib.sha256(
                json.dumps(
                    {
                        "query": rule["query"],
                        "modules": rule["modules"],
                        "dependencies": rule["dependencies"],
                        "dataset_hash": data["hash"],
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            try:
                if key not in cache:
                    pack = output / "evaluation" / row["stage"]["id"]
                    prepare_query(
                        pack,
                        rule["language"],
                        rule["query"],
                        rule["modules"],
                        rule["dependencies"],
                    )
                    cache[key] = evaluate(
                        root / "holdouts" / row["case"], pack, data, pack / "oracle"
                    )
                    row["evaluation_cache_hit"] = False
                else:
                    row["evaluation_cache_hit"] = True
                row["oracle"] = cache[key]
            except Exception as exc:
                row["oracle"] = {"status": "execution_error"}
                row["oracle_error"] = {"type": type(exc).__name__, "message": str(exc)}
        print(row["arm"], row["case"], row["oracle"]["status"], flush=True)
        (output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2)
        )


if __name__ == "__main__":
    main()
