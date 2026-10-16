"""Small deterministic development comparison; never rewrite the full experiment."""

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

from scripts.benchmarks.cqllm_materials import REPO, sha
from scripts.benchmarks.mechanical_pipeline import exclusive, save

SEED = "cqllm-prompt-v2-development-20261015"


def select_tasks(tasks, count):
    ordered = sorted(tasks, key=lambda t: sha256((SEED + t["id"]).encode()).hexdigest())
    selected, seen = [], set()
    for task in ordered:
        cwe = task["requirement"]["CWE-id"]
        if cwe in seen:
            continue
        selected.append(task)
        seen.add(cwe)
        if len(selected) == count:
            return selected
    raise ValueError("Not enough distinct CWE tasks")


def summarize(origin, root, tasks):
    rows = []
    for task in tasks:
        identity = task["id"]
        new = root / "arms/no_rag" / identity / "result.json"
        if not new.exists():
            continue
        old = json.loads(
            (origin / "arms/no_rag" / identity / "result.json").read_text()
        )
        row = json.loads(new.read_text())
        rows.append(
            {
                "task_id": identity,
                "cwe": task["requirement"]["CWE-id"],
                "v1_status": old["status"],
                "v2_status": row["status"],
                "v1_first_compile": bool(old.get("first_compile_success")),
                "v2_first_compile": bool(row.get("first_compile_success")),
                "v1_final_compile": bool(old.get("compile_success")),
                "v2_final_compile": bool(row.get("compile_success")),
                "v1_error": old.get("error"),
                "v2_error": row.get("error"),
                "v2_usage": row.get("usage"),
            }
        )
    summary = {
        "regime": "development pilot, not independent generalization or full rerun",
        "planned": len(tasks),
        "completed": len(rows),
        "cases": rows,
        "v1_first_compile": sum(r["v1_first_compile"] for r in rows),
        "v2_first_compile": sum(r["v2_first_compile"] for r in rows),
        "v1_final_compile": sum(r["v1_final_compile"] for r in rows),
        "v2_final_compile": sum(r["v2_final_compile"] for r in rows),
        "v2_statuses": dict(Counter(r["v2_status"] for r in rows)),
        "execution_and_semantics": "not_evaluated",
        "retrieval": "none; fixed common packaging/API guidance in versioned system prompt",
    }
    save(root / "summary.json", summary)
    return summary


def run(origin, root, count):
    from scripts.benchmarks.cqllm_generation import generate
    from scripts.benchmarks.realvuln_run import verify_implementation

    root.mkdir(parents=True, exist_ok=True)
    with exclusive(root / "pilot.lock"):
        verify_implementation(origin)
        manifest = json.loads((origin / "manifest.json").read_text())
        tasks = select_tasks(manifest["tasks"], count)
        paths = [
            REPO / "benchmarks/prompts/cqllm-rule.v2.txt",
            Path(__file__),
            Path(__file__).with_name("cqllm_generation.py"),
        ]
        hashes = {str(p.relative_to(REPO)): sha(p) for p in paths}
        parents = {
            task["id"]: sha(origin / "arms/no_rag" / task["id"] / "result.json")
            for task in tasks
        }
        protocol = {
            "origin": str(origin),
            "selection_seed": SEED,
            "tasks": tasks,
            "selection": "SHA256(seed+row_id) order; one task per CWE; independent of historical success/failure",
            "source_hashes": hashes,
            "v1_receipt_hashes": parents,
            "formal_results_unchanged": True,
            "no_hidden_execution_feedback": True,
            "development_exposure": "all source tasks already appeared in the formal batch; no holdout claim",
        }
        path = root / "protocol.json"
        if path.exists() and json.loads(path.read_text()) != protocol:
            raise RuntimeError("Frozen pilot inputs changed")
        save(path, protocol)
        config = json.loads((origin / "config.json").read_text())
        prompt = paths[0].read_text()
        config.update(
            prompt=prompt,
            prompt_version="cqllm-2",
            prompt_sha256=sha256(prompt.encode()).hexdigest(),
            model_tasks=count,
        )
        save(root / "config.json", config)
        streak = 0
        for task in tasks:
            verify_implementation(origin)
            if any(sha(REPO / name) != digest for name, digest in hashes.items()):
                raise RuntimeError("Pilot implementation changed")
            row = generate(task, "no_rag", root, config)
            summarize(origin, root, tasks)
            streak = streak + 1 if row.get("provider_interrupted") else 0
            if streak >= 3:
                raise RuntimeError(
                    "Three consecutive provider failures; paid work stopped"
                )
        save(root / "finished.json", {"status": "completed", "tasks": count})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=12, choices=range(1, 25))
    args = parser.parse_args()
    run(args.origin.resolve(), args.output.resolve(), args.count)


if __name__ == "__main__":
    main()
