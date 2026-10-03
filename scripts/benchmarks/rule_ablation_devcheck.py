"""Evaluate model-authored dev fixtures without approving/publishing any rule.

Deterministic identical (query, modules, fixtures, dependencies) evaluations are
cached; repetition is model generation stability, not repeated tool precision.
"""

import argparse
import hashlib
import json
from pathlib import Path

from app.adapters.codeql.custom import prepare_query
from scripts.benchmarks.rule_ablation_oracles import build_databases, evaluate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output
    cache_root = output / "dev-evaluation"
    cache_root.mkdir(exist_ok=True)
    records_directory = output / "records"
    if records_directory.exists():
        rows = [
            json.loads(path.read_text()) for path in records_directory.glob("*.json")
        ]
    else:
        rows = json.loads((output / "report.json").read_text())["records"]
    for row in rows:
        if row.get("dev_oracle") or row.get("dev_error"):
            continue
        if not row["rules"]:
            row["dev_oracle"] = {"status": "not_generated"}
        else:
            rule = row["rules"][0]
            key = hashlib.sha256(
                json.dumps(
                    {
                        k: rule[k]
                        for k in (
                            "query",
                            "modules",
                            "fixtures",
                            "dependencies",
                            "language",
                        )
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            directory = cache_root / key
            directory.mkdir(exist_ok=True)
            cached = directory / "result.json"
            if cached.exists():
                result = json.loads(cached.read_text())
            else:
                data = {
                    "id": key,
                    "language": rule["language"],
                    "fixtures": rule["fixtures"],
                    "hash": key,
                }
                try:
                    pack = directory / "pack"
                    prepare_query(
                        pack,
                        rule["language"],
                        rule["query"],
                        rule["modules"],
                        rule["dependencies"],
                    )
                    build_databases(directory, data)
                    result = {
                        "dev_oracle": evaluate(
                            directory, pack, data, directory / "oracle"
                        )
                    }
                except Exception as exc:
                    result = {
                        "dev_error": {"type": type(exc).__name__, "message": str(exc)}
                    }
                cached.write_text(json.dumps(result, ensure_ascii=False, indent=2))
            row.update(result)
            row["dev_cache_key"] = key
        if records_directory.exists():
            (records_directory / f"{row['stage']['id']}.json").write_text(
                json.dumps(row, ensure_ascii=False, indent=2)
            )
        else:
            report = json.loads((output / "report.json").read_text())
            report["records"] = rows
            (output / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2)
            )
        print(
            row["arm"],
            row["case"],
            row.get("dev_oracle", {}).get("status", "error"),
            flush=True,
        )
    report = json.loads((output / "report.json").read_text())
    report["records"] = rows
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    main()
