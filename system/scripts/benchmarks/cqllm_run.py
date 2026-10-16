"""Independent 596-task pipeline: download in parallel, pair, compile, evaluate."""

import argparse
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from scripts.benchmarks.cqllm_materials import freeze
from scripts.benchmarks.mechanical_pipeline import exclusive, save


def summarize(root, phase):
    rows = [json.loads(p.read_text()) for p in root.glob("arms/*/*/result.json")]
    evaluations = [
        json.loads(p.read_text()) for p in root.glob("arms/*/*/evaluation.json")
    ]
    output = {
        "phase": phase,
        "planned_tasks": 596,
        "generation_receipts": len(rows),
        "evaluation_receipts": len(evaluations),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "arms": {},
        "semantic_correctness": "not_evaluated_no_independent_gold",
    }
    for arm in ("no_rag", "current_rag"):
        tasks = [r for r in rows if r["arm"] == arm]
        execution = [r for r in evaluations if r["arm"] == arm]
        output["arms"][arm] = {
            "frozen_rows": 298,
            "attempted": len(tasks),
            "statuses": dict(Counter(r["status"] for r in tasks)),
            "first_compile_pass": sum(
                r.get("first_compile_success", False) for r in tasks
            ),
            "final_compile_pass": sum(r.get("compile_success", False) for r in tasks),
            "execution_pass": sum(r.get("execution_success", False) for r in execution),
            "calls": sum(r.get("usage", {}).get("calls", 0) for r in tasks),
            "input_tokens": sum(
                r.get("usage", {}).get("input_tokens", 0) for r in tasks
            ),
            "output_tokens": sum(
                r.get("usage", {}).get("output_tokens", 0) for r in tasks
            ),
        }
    save(root / "summary.json", output)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with exclusive(root / "cqllm.lock"):
        from scripts.benchmarks.cqllm_evaluate import evaluate, prepare_database
        from scripts.benchmarks.cqllm_generation import (
            configuration,
            corpus_identity,
            generate,
        )
        from scripts.benchmarks.realvuln_run import verify_implementation

        manifest = freeze(root)
        verify_implementation(root)
        config = configuration()
        config_path = root / "config.json"
        if config_path.exists() and json.loads(config_path.read_text()) != config:
            raise RuntimeError("Frozen model/prompt/dependencies/corpus changed")
        save(config_path, config)
        # CodeQL author database is evaluator-only and never enters retrieval or prompts.
        with ThreadPoolExecutor(max_workers=1) as executor:
            download = executor.submit(prepare_database, root)
            results, consecutive_failures = [], 0
            for index, task in enumerate(manifest["tasks"]):
                # Alternate arm order; preserve every row despite duplicate Query_id values.
                arms = (
                    manifest["arms"]
                    if index % 2 == 0
                    else list(reversed(manifest["arms"]))
                )
                for arm in arms:
                    verify_implementation(root)
                    if download.done() and download.exception():
                        raise RuntimeError(
                            "Author database preparation failed; stop new model tasks"
                        ) from download.exception()
                    if corpus_identity() != config["corpus_identity"]:
                        raise RuntimeError(
                            "Shared corpus changed during paired experiment"
                        )
                    result = generate(task, arm, root, config)
                    results.append(result)
                    summarize(root, "generation")
                    consecutive_failures = (
                        consecutive_failures + 1
                        if result.get("provider_interrupted")
                        else 0
                    )
                    if consecutive_failures >= 3:
                        save(
                            root / "blocked.json",
                            {
                                "reason": "three_consecutive_provider_failures",
                                "task": task["id"],
                            },
                        )
                        raise RuntimeError(
                            "Provider outage; three failed tasks retained, no more paid requests"
                        )
            database = download.result()
            for result in results:
                evaluate(result, root, database)
                summarize(root, "evaluation")
        summary = summarize(root, "finished")
        if (
            summary["generation_receipts"] != 596
            or summary["evaluation_receipts"] != 596
        ):
            raise RuntimeError("Full CQLLM task matrix incomplete")


if __name__ == "__main__":
    main()
