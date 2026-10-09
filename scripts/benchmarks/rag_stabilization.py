"""Freeze current corpus, compare v7 and four components on unchanged old oracles."""

import argparse
import hashlib
import json
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from app.services.context_materials import save_json

from scripts.benchmarks.legacy_rag_comparison import run_one
from scripts.benchmarks.legacy_rag_dataset import ROOT, freeze, verify_frozen
from scripts.benchmarks.legacy_rag_scoring import summarize

ARMS = {
    "full_v8": {},
    "no_scope_context": {"source_preparation_context": False},
    "early_rag": {"rag_before_inspection": True},
    "bm25_v8": {"retrieval_mode": "bm25"},
    "full_v7": {},
    "no_compact": {"compact_context": False},
    "free_ql": {"generation_constraint": False},
    "no_progress": {"progress_feedback": False},
    "bm25_v7": {"retrieval_mode": "bm25"},
}


REPORT_LOCK = Lock()


def report(output, manifest):
    rows = [json.loads(p.read_text()) for p in (output / "records").glob("*.json")]
    result = {
        "manifest": manifest,
        "groups": summarize(rows),
        "records": rows,
        "complete": len(rows) == 18 * len(manifest["arms"]),
        "interpretation": "Six task families repeated three times, not 18 independent vulnerabilities. Hidden data unchanged and never used for refinement. Full current version versus old K is a pipeline comparison. Component arms hold current prompt/corpus/roles/budgets constant. Timing depends on local caches and interleaved execution; report successful-request medians separately.",
    }
    with REPORT_LOCK:
        save_json(output / "report.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--version", choices=["7", "8"], default="7")
    parser.add_argument("--reference-controls", type=Path)
    parser.add_argument("--wait-corpus", action="store_true")
    parser.add_argument(
        "--arms", default="old_K,full_v7,no_compact,free_ql,no_progress,bm25_v7"
    )
    args = parser.parse_args()
    if args.wait_corpus:
        corpus_path = ROOT / "artifacts/materials/rag-corpus-v4/manifest.json"
        start = time.monotonic()
        while not corpus_path.exists() or "summary" not in json.loads(
            corpus_path.read_text()
        ):
            if time.monotonic() - start > 3600:
                raise RuntimeError("Corpus not ready; no benchmark requests were made")
            time.sleep(10)
    output = args.output.resolve()
    selected = args.arms.split(",")
    if not set(selected).issubset({"old_K", *ARMS}):
        raise RuntimeError("Unknown arm")
    if output.exists() and not args.resume:
        raise RuntimeError("Existing experiment must be resumed, never overwritten")
    output.mkdir(parents=True, exist_ok=True)
    (output / "records").mkdir(exist_ok=True)
    logging.basicConfig(filename=output / "execution.log", level=logging.WARNING)
    if args.resume:
        manifest = json.loads((output / "manifest.json").read_text())
    else:
        manifest = freeze(output, 3)
        v4 = json.loads(
            (ROOT / "artifacts/materials/rag-corpus-v4/manifest.json").read_text()
        )
        manifest["corpus_document_ids"] = sorted(
            {
                r["document_id"]
                for corpus in ("reference", "rule_example")
                for r in v4[corpus]
            }
        )
        # Reuse original development audits, while freezing THIS corpus independently.
        previous = json.loads(
            (
                ROOT / "artifacts/benchmarks/legacy-rag-deployed-20261004/manifest.json"
            ).read_text()
        )
        manifest["owner"] = previous["owner"]
        manifest["audits"] = previous["audits"]
        manifest["arms"] = {
            a: "Fresh old K frozen retrieval"
            if a == "old_K"
            else f"v{args.version} {ARMS[a]}"
            for a in selected
        }
        manifest["arm_versions"] = {a: args.version for a in selected if a != "old_K"}
        manifest["arm_experiments"] = {a: ARMS[a] for a in selected if a != "old_K"}
        manifest["prompt_hashes"][args.version] = hashlib.sha256(
            (ROOT / f"backend/app/prompts/rule.v{args.version}.txt").read_bytes()
        ).hexdigest()
        manifest["source_audits_reference"] = str(
            ROOT / "artifacts/benchmarks/legacy-rag-deployed-20261004/manifest.json"
        )
        paths = [
            "backend/app/services/rule_synthesis.py",
            "backend/app/services/rule_context.py",
            "backend/app/services/semantic_inspection.py",
            "backend/app/services/inspection_progress.py",
            "backend/app/services/rule_materials.py",
            "backend/app/adapters/codeql/grounded_spec.py",
            "backend/app/adapters/retrieval/dual_corpus.py",
            "backend/app/adapters/retrieval/knowledge.py",
            "backend/app/adapters/retrieval/quality.py",
            "backend/app/workflows/rules.py",
            "backend/app/services/rule_feedback.py",
            "backend/app/services/rule_preparation_context.py",
            "backend/app/services/rule_output.py",
            "backend/app/services/rules.py",
            "backend/app/services/rules_execution.py",
            "backend/app/adapters/ai/provider.py",
            "backend/app/services/context_materials.py",
            "scripts/benchmarks/legacy_rag_scoring.py",
            "scripts/benchmarks/legacy_rag_comparison.py",
        ]
        manifest["implementation_hashes"] = {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths
        }
        if args.reference_controls:
            reference = args.reference_controls.resolve()
            prior = json.loads((reference / "manifest.json").read_text())
            verify_frozen(reference, prior)
            for key in (
                "policy",
                "cases",
                "cli",
                "hidden_manifest_hash",
                "old_records_hash",
            ):
                if manifest[key] != prior[key]:
                    raise RuntimeError(f"Reference control mismatch: {key}")
            controls = []
            for path in (reference / "records").glob("*.json"):
                row = json.loads(path.read_text())
                if row["arm"] == "old_K":
                    controls.append((path, row))
            if len(controls) != 18 or "old_K" not in selected:
                raise RuntimeError("Exactly eighteen completed old controls required")
            for path, row in controls:
                row["reference_record"] = str(path)
                save_json(output / "records" / path.name, row)
            manifest["reference_controls"] = str(reference)
            manifest["reference_note"] = (
                "18 unchanged old controls reused; all other arms are fresh, randomized/interleaved. Old/new group timing is not a contemporaneous latency comparison."
            )
        save_json(output / "manifest.json", manifest)
    verify_frozen(output, manifest)
    cases = list(manifest["cases"])
    random.Random(manifest["seed"]).shuffle(cases)

    def run_case(index, case):
        rng = random.Random(manifest["seed"] + index)
        for number in range(1, 4):
            arms = list(manifest["arms"])
            rng.shuffle(arms)
            for arm in arms:
                run_one(output, manifest, case, arm, number)
                report(output, manifest)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_case, i, c) for i, c in enumerate(cases)]
        for future in as_completed(futures):
            future.result()
    verify_frozen(output, manifest)
    if any(
        hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h
        for p, h in manifest["implementation_hashes"].items()
    ):
        raise RuntimeError("Implementation changed during frozen benchmark")
    save_json(
        output / "freeze-verification.json",
        {
            "status": "passed",
            "implementation_hashes": manifest["implementation_hashes"],
            "complete_records": len(list((output / "records").glob("*.json"))),
        },
    )
    print(
        json.dumps(report(output, manifest)["groups"], ensure_ascii=False), flush=True
    )


if __name__ == "__main__":
    main()
