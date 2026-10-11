"""Freeze fresh same-distribution samples; model runner never reads evaluator gold."""

import argparse
import ast
import hashlib
import json
import random
import shutil
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT
    / "benchmark-data/model-inputs/20261005-loader-correction/owasp-python-loader-fixed"
)
GOLD = (
    ROOT
    / "benchmark-data/evaluator-only/experiments/20261005-calibration-v1/owasp-labels.json"
)
OLD = ROOT / "artifacts/research/owasp48/20261007-evolution"


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Shape(ast.NodeTransformer):
    def __init__(self):
        self.names = {}

    def name(self, value):
        return self.names.setdefault(value, "v" + str(len(self.names)))

    def visit_Name(self, node):
        node.id = self.name(node.id)
        return node

    def visit_arg(self, node):
        node.arg = self.name(node.arg)
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.name = self.name(node.name)
        return self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            node.value = "STRING"
        elif isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            node.value = 0
        return node


def shape(row):
    tree = Shape().visit(ast.parse((SOURCE / row["file"]).read_text()))
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()


def exclusions():
    paths = [
        ROOT
        / "artifacts/research/owasp-discovery/20261007-pilot-preparation/evaluator-selection.json"
    ]
    paths += sorted((OLD / "samples").glob("*/evaluator-selection.json"))
    used = set()
    for path in paths:
        used.update(row["file"] for row in json.loads(path.read_text())["selected"])
    return used, paths


def make_sample(output, role, selected, seed, shapes, exposed_shapes):
    directory = output / "samples" / role
    source = directory / "source"
    chosen = {r["file"] for r in selected}
    for path in SOURCE.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(SOURCE)
        if (
            relative.parts[0] == "testcode"
            and path.name != "__init__.py"
            and relative.as_posix() not in chosen
        ):
            continue
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    for path in source.rglob("*.py"):
        ast.parse(path.read_text())
    assert len(list((source / "testcode").glob("Case*.py"))) == 48
    batches = [
        {
            "group_id": f"batch-{i // 4 + 1:02d}",
            "case_paths": [r["file"] for r in selected[i : i + 4]],
        }
        for i in range(0, 48, 4)
    ]
    save(directory / "model-batches.json", {"source": str(source), "batches": batches})
    hashes = {
        p.relative_to(source).as_posix(): sha(p)
        for p in source.rglob("*")
        if p.is_file()
    }
    overlap = sum(shapes[r["file"]] in exposed_shapes for r in selected)
    save(
        directory / "evaluator-selection.json",
        {
            "selected": selected,
            "seed": seed,
            "role": role,
            "model_batches": batches,
            "source_hashes": hashes,
            "distribution": dict(Counter(r["category"] for r in selected)),
            "structural_prior_overlap_cases": overlap,
            "shape_groups": {r["file"]: shapes[r["file"]] for r in selected},
        },
    )
    return {
        "role": role,
        "case_count": 48,
        "source": str(source),
        "source_files": len(hashes),
        "structural_prior_overlap_cases": overlap,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("Never overwrite a prepared campaign")
    labels = json.loads(GOLD.read_text())
    used, history = exclusions()
    all_categories = sorted({r["category"] for r in labels})
    available = {
        c: {
            str(flag): sum(
                r["category"] == c and r["vulnerable"] == flag and r["file"] not in used
                for r in labels
            )
            for flag in (True, False)
        }
        for c in all_categories
    }
    categories = [
        c
        for c in all_categories
        if all(available[c][str(flag)] >= 4 for flag in (True, False))
    ]
    assert len(categories) == 11
    shapes = {r["file"]: shape(r) for r in labels}
    prior = {shapes[file] for file in used}
    samples = []
    for index, seed in enumerate((2026100948, 2026101048)):
        rng = random.Random(seed)
        extras = [
            c
            for c in categories
            if all(
                sum(
                    r["category"] == c
                    and r["vulnerable"] == flag
                    and r["file"] not in used
                    for r in labels
                )
                >= 2 * (2 - index) + 1
                for flag in (True, False)
            )
        ]
        rng.shuffle(extras)
        extras = set(extras[:2])
        assert len(extras) == 2
        selected = []
        for category in categories:
            for flag in (True, False):
                eligible = [
                    r
                    for r in labels
                    if r["category"] == category
                    and r["vulnerable"] == flag
                    and r["file"] not in used
                ]
                rng.shuffle(eligible)
                eligible.sort(key=lambda r: shapes[r["file"]] in prior)
                count = 3 if category in extras else 2
                if len(eligible) < count:
                    raise RuntimeError("Insufficient disjoint category/label cases")
                selected += eligible[:count]
        rng.shuffle(selected)
        assert len(selected) == 48 and sum(r["vulnerable"] for r in selected) == 24
        assert not ({r["file"] for r in selected} & used)
        samples.append(
            make_sample(
                output, f"validation-{index + 1:02d}", selected, seed, shapes, prior
            )
        )
        used.update(r["file"] for r in selected)
        prior.update(shapes[r["file"]] for r in selected)
    old = json.loads((OLD / "protocol.json").read_text())
    implementation = {
        p.relative_to(ROOT).as_posix(): sha(p)
        for directory in (
            "backend/app",
            "scripts/benchmarks",
            "benchmark-data/experiments/owasp48",
        )
        for p in (ROOT / directory).rglob("*")
        if p.is_file() and p.suffix in {".py", ".txt"}
    }
    save(
        output / "protocol.json",
        {
            "experiment_id": output.name,
            "samples": samples,
            "packs": old["packs"],
            "codeql_cli": subprocess.check_output(
                ["codeql", "version", "--format=json"], text=True
            ).strip(),
            "scorer_sha256": sha(ROOT / "scripts/benchmarks/formal_scoring.py"),
            "gold_sha256": sha(GOLD),
            "implementation_hashes": implementation,
            "locks": {
                p: sha(ROOT / p) for p in ("uv.lock", "frontend/package-lock.json")
            },
            "historical_exclusions": {
                p.relative_to(ROOT).as_posix(): sha(p) for p in history
            },
            "available_after_prior_exclusion": available,
            "fresh_categories": categories,
            "exhausted_categories_not_resampled": [
                c for c in all_categories if c not in categories
            ],
            "concurrency": 3,
            "stage_caps": {"calls": 28, "tokens": 500000, "seconds": 600},
            "versions": {"scout": "7", "review": "9"},
            "planned_executions": 2,
            "production_changes_allowed": False,
            "labels_into_model": False,
            "claim": "Fresh file-disjoint OWASP same-distribution validation; not independent frameworks or training-unseen evidence. Score only after both runs; no score-driven tuning.",
        },
    )
    print(
        json.dumps(
            {"samples": samples, "prior_exclusion_count": len(used) - 96},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
