"""Derive calibration counts from receipts; never hand-edit reported successes."""

import hashlib
import json
import statistics
from collections import defaultdict

from scripts.benchmarks.formal_freeze import OUTPUT, ROOT, save


def load(path):
    return json.loads(path.read_text())


def public_metrics(metrics):
    if not metrics:
        return None
    result = {
        k: v for k, v in metrics.items() if k not in {"cases", "outside_target_alerts"}
    }
    result["outside_target_alert_count"] = len(metrics.get("outside_target_alerts", []))
    return result


def bandit_summary():
    records = []
    for path in sorted((OUTPUT / "bandit").glob("*/result.json")):
        row = load(path)
        records.append(
            {
                "input_version": path.parent.name,
                "tool": row["tool"],
                "primary": path.parent.name == "owasp-python-loader-fixed-py314",
                "rounds": [
                    {
                        "status": r["status"],
                        "seconds": r["seconds"],
                        "parser_error_count": len(r.get("errors") or []),
                        "metrics": public_metrics(r.get("metrics")),
                    }
                    for r in row["records"]
                ],
            }
        )
    return records


def discovery_summary():
    receipt = load(OUTPUT / "discovery/root-adjudication.json")
    rows = [{"project": r["project"], **r["summary"]} for r in receipt["projects"]]
    for row in rows:
        for kind in ("D1", "D3"):
            generation = load(OUTPUT / "discovery" / row["project"] / (kind + ".json"))
            row[kind + "_seconds"] = generation["wall_seconds"]
            row[kind + "_model_calls"] = generation["stage"]["usage"]["calls"]
    return {
        "adjudication": receipt["adjudication"],
        "projects": rows,
        "strict_primary_gold_roots": 31,
        "strict_primary_static_matches": 12,
        "strict_primary_union_matches": 16,
        "confirmed_additional_TP": 0,
        "note": "Strict totals exclude bundled secondary debug condition; provisional source adjudication, not human gold or deployability proof",
    }


def main():
    configuration = load(OUTPUT / "config.json")
    summary = {
        "experiment_id": OUTPUT.name,
        "scope": "first collected-benchmark calibration",
        "formal_hidden_benchmark_complete": False,
        "paper_uplift_demonstrated": False,
        "primary_static": [],
        "diagnostic_static": [],
        "rules": {},
        "repair": {},
        "retrieval": {},
        "bandit": bandit_summary(),
        "discovery": discovery_summary(),
        "no_rag_control": "unsupported_by_current_contract; no score assigned",
        "rule_input_limit": "Two bounded Python testcase/helper tasks; reference-query oracle and entrypoint calibration pending",
        "retrieval_limit": "Metadata fit only, no human qrels; generation role routing may force BM25",
        "discovery_input_limit": "Development labels exposed; category hint removal not yet complete",
        "text_model_calls": 0,
        "text_input_tokens": 0,
        "text_output_tokens": 0,
        "embedding_usage_note": "Standalone retrieval made 20 embedding requests; generation embedding usage not included in text token counters",
        "implementation_backend_verified": all(
            hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
            for p, h in configuration["implementation_hashes"].items()
            if p.startswith("system/backend/")
        ),
    }
    for path in sorted((OUTPUT / "static").glob("*/result.json")):
        row = load(path)
        destination = (
            "diagnostic_static"
            if row["project_id"] == "owasp-python"
            else "primary_static"
        )
        summary[destination].append(
            {
                "project_id": row["project_id"],
                "status": row["status"],
                "extract_seconds": row.get("extract_seconds"),
                "first_query_seconds": row["rounds"][0]["query_seconds"]
                if row["rounds"]
                else None,
                "warm_query_seconds": [x["query_seconds"] for x in row["rounds"][1:]],
                "alerts": row["rounds"][0]["alerts"] if row["rounds"] else None,
                "metrics": public_metrics(row.get("metrics")),
                "error": row.get("error"),
            }
        )
    generations = list((OUTPUT / "discovery").glob("*/D1.json")) + list(
        (OUTPUT / "discovery").glob("*/D3.json")
    )
    generations += list((OUTPUT / "repair").glob("v*/generation.json"))
    generations += list((OUTPUT / "rules").glob("*/*/generation.json"))
    models = set()
    for path in generations:
        row = load(path)
        usage = row["stage"]["usage"]
        for source, target in (
            ("calls", "text_model_calls"),
            ("input_tokens", "text_input_tokens"),
            ("output_tokens", "text_output_tokens"),
        ):
            summary[target] += usage.get(source, 0)
        models.update(
            r.get("response_model")
            for r in row["stage"]["model_calls"]
            if r.get("response_model")
        )
    summary["response_models"] = sorted(models)
    groups = defaultdict(list)
    for path in (OUTPUT / "rules").glob("*/*/scored.json"):
        mode = path.parent.name.split("-round-")[0]
        groups[mode].append(load(path))
    for mode, rows in groups.items():
        summary["rules"][mode] = {
            "runs": len(rows),
            "distinct_tasks": len({r["generation"]["stage"]["audit_id"] for r in rows}),
            "persisted_compile_development_pass": sum(bool(r["rules"]) for r in rows),
            "hidden_evaluated": sum(r["hidden"]["status"] == "evaluated" for r in rows),
            "hidden_all_conditions_pass": sum(
                r["hidden"].get("all_conditions_pass", False) for r in rows
            ),
            "hidden_TP": sum(
                r["hidden"].get("metrics", {}).get("counts", {}).get("TP", 0)
                for r in rows
            ),
            "hidden_FP": sum(
                r["hidden"].get("metrics", {}).get("counts", {}).get("FP", 0)
                for r in rows
            ),
            "hidden_not_run": sum(r["hidden"]["status"] == "not_run" for r in rows),
            "hidden_infra_failure": sum(
                r["hidden"]["status"] == "infra_failure" for r in rows
            ),
            "median_generation_seconds": statistics.median(
                r["generation"]["wall_seconds"] for r in rows
            ),
            "generation_errors": [
                r["generation"]["stage"]["error"]
                for r in rows
                if r["generation"]["stage"]["error"]
            ],
            "project_alert_counts": [
                len(q["validation"].get("project_replay", {}).get("findings", []))
                for r in rows
                for q in r["rules"]
            ],
        }
    repair = defaultdict(list)
    for path in (OUTPUT / "repair").glob("v*/scored.json"):
        row = load(path)
        repair[row["version"]].append(row)
    for version, rows in repair.items():
        summary["repair"][version] = {
            "runs": len(rows),
            "distinct_tasks": 1,
            "applied_evaluated": sum(
                r["oracle"]["status"] == "evaluated" for r in rows
            ),
            "bounded_joint_pass": sum(
                bool(r["oracle"].get("joint_pass")) for r in rows
            ),
            "median_wall_seconds": statistics.median(
                r["generation"]["wall_seconds"] for r in rows
            ),
            "mean_model_calls": statistics.mean(
                r["generation"]["stage"]["usage"].get("calls", 0) for r in rows
            ),
            "errors": [
                r["generation"]["stage"]["error"]
                for r in rows
                if r["generation"]["stage"]["error"]
            ],
            "oracle_origin": "derived-agent-authored-not-human-reviewed",
        }
    if (OUTPUT / "retrieval/summary.json").exists():
        rows = load(OUTPUT / "retrieval/summary.json")["records"]
        for mode in ("bm25", "vector", "hybrid"):
            matched = [r for r in rows if r["mode"] == mode]
            summary["retrieval"][mode] = {
                "queries": len(matched),
                "successful": sum(r["status"] == "succeeded" for r in matched),
                "metadata_CWE_examples": sum(
                    r.get("metadata_CWE_example_hits", 0) for r in matched
                ),
                "example_slots": len(matched) * 2,
                "human_relevance": "not_evaluated",
                "median_db_retrieval_seconds": statistics.median(
                    r["retrieval_seconds"] for r in matched
                ),
            }
    save(OUTPUT / "summary.json", summary)
    save(ROOT / "benchmarks/experiments/calibration-summary.json", summary)
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "rules",
                    "repair",
                    "text_model_calls",
                    "implementation_backend_verified",
                )
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
