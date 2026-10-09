"""Score only the exact original hidden data, outside the generation loop."""

import json
import statistics
import time

from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.custom import prepare_query
from app.domain.audit import AuditError
from app.services.context_materials import save_json

from scripts.benchmarks.legacy_rag_dataset import MAIN
from scripts.benchmarks.rule_ablation_oracles import evaluate


def score(output, row):
    if not row["rules"]:
        row["oracle"] = {"status": "not_generated"}
        return row
    rule = row["rules"][0]
    stage_id = row["stage"]["id"]
    directory = output / "evaluation" / stage_id
    pack = directory / "pack"
    data = json.loads((output / "hidden-manifest.json").read_text())[row["case"]]
    start = time.perf_counter()
    try:
        prepare_query(
            pack, rule["language"], rule["query"], rule["modules"], rule["dependencies"]
        )
        row["oracle"] = evaluate(
            MAIN / "holdouts" / row["case"], pack, data, directory / "oracle"
        )
    except (AuditError, OSError, ValueError) as exc:
        row["oracle"] = {
            "status": "error",
            "error": {"type": type(exc).__name__, "message": str(exc)[:1000]},
        }
    row["evaluation_seconds"] = time.perf_counter() - start
    row["end_to_end_passed"] = (
        row["oracle"]["status"] == "passed"
        and rule["validation"].get("development", {}).get("status") == "passed"
    )
    return row


def summarize(rows):
    groups = {}
    for arm in sorted({r["arm"] for r in rows}):
        chosen = [r for r in rows if r["arm"] == arm]
        case_names = sorted({r["case"] for r in chosen})
        executed = [
            r
            for r in chosen
            if r.get("oracle", {}).get("status") in {"passed", "failed"}
        ]
        tp = sum(r["oracle"]["tp"] for r in executed)
        fp = sum(r["oracle"]["fp"] for r in executed)
        fn = sum(r["oracle"]["fn"] for r in executed)
        group = {
            "requests": len(chosen),
            "independent_tasks": len(case_names),
            "observed_compile_passed": sum(
                r.get("observed_compile_passed", False) for r in chosen
            ),
            "generated": sum(bool(r["rules"]) for r in chosen),
            "development_passed": sum(
                r.get("observed_development_passed", False) for r in chosen
            ),
            "hidden_executed": len(executed),
            "hidden_passed": sum(
                r.get("oracle", {}).get("status") == "passed" for r in chosen
            ),
            "end_to_end_passed": sum(r.get("end_to_end_passed", False) for r in chosen),
            "conditional_tp": tp,
            "conditional_fp": fp,
            "conditional_fn": fn,
            "conditional_precision": tp / (tp + fp) if tp + fp else None,
            "conditional_recall": tp / (tp + fn) if tp + fn else None,
            "generation_median_seconds": statistics.median(
                r["generation_seconds"] for r in chosen
            ),
            "total_median_seconds": statistics.median(
                r["generation_seconds"] + r.get("evaluation_seconds", 0) for r in chosen
            ),
            "model_calls": sum(r["stage"]["usage"].get("calls", 0) for r in chosen),
            "input_tokens": sum(
                r["stage"]["usage"].get("input_tokens", 0) for r in chosen
            ),
            "output_tokens": sum(
                r["stage"]["usage"].get("output_tokens", 0) for r in chosen
            ),
            "response_models": sorted(
                {
                    c.get("response_model")
                    for r in chosen
                    for c in r["stage"]["model_calls"]
                    if c.get("response_model")
                }
            ),
            "per_case": {},
        }
        for name in case_names:
            part = [r for r in chosen if r["case"] == name]
            group["per_case"][name] = {
                "requests": len(part),
                "generated": sum(bool(r["rules"]) for r in part),
                "hidden_passed": sum(
                    r.get("oracle", {}).get("status") == "passed" for r in part
                ),
                "end_to_end_passed": sum(
                    r.get("end_to_end_passed", False) for r in part
                ),
            }
        groups[arm] = group
    return groups


def observed(stage_id):
    files = (ArtifactStore().directory(stage_id) / "node-timings").glob("*.json")
    rows = [json.loads(path.read_text()) for path in files]
    return {
        "observed_compile_passed": any(
            r["node"] == "compile_draft" and r.get("candidate_passed") for r in rows
        ),
        "observed_development_passed": any(
            r["node"] == "execute_development" and r.get("candidate_passed")
            for r in rows
        ),
    }


def publish_report(output, manifest):
    rows = [json.loads(p.read_text()) for p in (output / "records").glob("*.json")]
    rows.sort(key=lambda r: (r["case"], r["round"], r["arm"]))
    report = {
        "manifest": manifest,
        "groups": summarize(rows),
        "records": rows,
        "complete": len(rows) == 36,
        "interpretation": "Six repeated development semantic families. Original hidden hashes unchanged. Whole-pipeline comparison; no population accuracy, isolated RAG causality, or automatic publication claim.",
    }
    save_json(output / "report.json", report)
    return report
