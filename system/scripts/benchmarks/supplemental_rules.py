"""Execute frozen historical full-v8 rules on newly authored flow probes."""

import argparse
import json
import time
from pathlib import Path

from app.adapters.codeql.custom import prepare_query
from app.adapters.codeql.scanner import CodeQLScanner
from app.domain.audit import AuditError

from scripts.benchmarks.rule_ablation_oracles import build_databases, evaluate
from scripts.benchmarks.supplemental_prepare import ROOT, save, sha
from scripts.benchmarks.supplemental_rule_cases import datasets

REFERENCE = ROOT / "artifacts/benchmarks/rag-stabilization-v8-20261004/report.json"


def prepare(output):
    if output.exists():
        raise RuntimeError("Never overwrite a frozen holdout campaign")
    original = json.loads(REFERENCE.read_text())
    records = [r for r in original["records"] if r["arm"] == "full_v8"]
    assert len(records) == 18
    assert all(len(r["rules"]) == 1 for r in records)
    save(output / "frozen-rules.json", records)
    cases = datasets()
    for family, data in cases.items():
        directory = output / "holdouts" / family
        save(directory / "dataset.json", data)
        data["hash"] = sha(directory / "dataset.json")
    save(output / "hidden-manifest.json", cases)
    save(
        output / "config.json",
        {
            "experiment_id": output.parent.name + "-rule-holdout",
            "reference_report": REFERENCE.relative_to(ROOT).as_posix(),
            "reference_report_sha256": sha(REFERENCE),
            "frozen_rules_sha256": sha(output / "frozen-rules.json"),
            "hidden_manifest_sha256": sha(output / "hidden-manifest.json"),
            "runner_sha256": sha(Path(__file__)),
            "generator_sha256": sha(
                ROOT / "system/scripts/benchmarks/supplemental_rule_cases.py"
            ),
            "codeql_cli": CodeQLScanner().version(),
            "implementation_hashes": {
                p.relative_to(ROOT).as_posix(): sha(p)
                for p in (ROOT / "system/backend/app").rglob("*.py")
            },
            "generated_rules": 18,
            "independent_families": 6,
            "new_model_calls": 0,
            "new_generation_requests": 0,
            "auto_publish": False,
            "formal_gold": False,
            "scope": "Historical fixed vulnerability-detector rules on new derived semantic probes; not deployed review-anchor purpose or isolated RAG causality",
        },
    )


def execute(output):
    config = json.loads((output / "config.json").read_text())
    assert sha(REFERENCE) == config["reference_report_sha256"]
    assert sha(output / "frozen-rules.json") == config["frozen_rules_sha256"]
    assert sha(output / "hidden-manifest.json") == config["hidden_manifest_sha256"]
    assert sha(Path(__file__)) == config["runner_sha256"]
    assert (
        sha(ROOT / "system/scripts/benchmarks/supplemental_rule_cases.py")
        == config["generator_sha256"]
    )
    assert all(sha(ROOT / p) == h for p, h in config["implementation_hashes"].items())
    cases = json.loads((output / "hidden-manifest.json").read_text())
    rows = json.loads((output / "frozen-rules.json").read_text())
    records = []
    for row in rows:
        family = "-".join(row["case"].split("-")[:2])
        directory = output / "runs" / family / str(row["round"])
        saved = directory / "result.json"
        if saved.exists():
            records.append(json.loads(saved.read_text()))
            continue
        began = time.perf_counter()
        rule = row["rules"][0]
        item = {
            "family": family,
            "historical_round": row["round"],
            "historical_stage_id": row["stage"]["id"],
            "query_hash": rule["query_hash"],
            "purpose": rule["purpose"],
            "new_model_calls": 0,
            "formal_gold": False,
        }
        try:
            data = cases[family]
            build_databases(output / "holdouts" / family, data)
            pack = directory / "pack"
            prepare_query(
                pack,
                rule["language"],
                rule["query"],
                rule["modules"],
                rule["dependencies"],
            )
            item["oracle"] = evaluate(
                output / "holdouts" / family, pack, data, directory / "oracle"
            )
        except (AuditError, OSError, ValueError) as exc:
            item["oracle"] = {"status": "error", "error_type": type(exc).__name__}
        item["seconds"] = time.perf_counter() - began
        save(saved, item)
        records.append(item)
        save(
            output / "report.json",
            {"records": records, "formal_gold": False, "new_model_calls": 0},
        )
        print(
            json.dumps(
                {
                    "family": family,
                    "round": row["round"],
                    "oracle": item["oracle"]["status"],
                }
            ),
            flush=True,
        )
    assert all(sha(ROOT / p) == h for p, h in config["implementation_hashes"].items())
    save(
        output / "integrity.json",
        {"production_unchanged": True, "rules_unchanged": True, "published": False},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "execute"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    {"prepare": prepare, "execute": execute}[args.action](args.output.resolve())


if __name__ == "__main__":
    main()
