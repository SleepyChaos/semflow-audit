"""Pre-register disjoint balanced samples and isolated model-visible source trees."""

import ast
import hashlib
import json
import random
import shutil
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts/research/owasp48/20261007-evolution"
SOURCE = (
    ROOT
    / "benchmark-data/model-inputs/20261005-loader-correction/owasp-python-loader-fixed"
)
GOLD = (
    ROOT
    / "benchmark-data/evaluator-only/experiments/20261005-calibration-v1/owasp-labels.json"
)


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


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


def main():
    if (OUT / "protocol.json").exists():
        raise RuntimeError("Existing campaign must not be reselected")
    labels = json.loads(GOLD.read_text())
    old = json.loads(
        (
            ROOT
            / "artifacts/research/owasp-discovery/20261007-pilot-preparation/evaluator-selection.json"
        ).read_text()
    )["selected"]
    used = {r["file"] for r in old}
    categories = sorted({r["category"] for r in labels})
    shapes = {r["file"]: shape(r) for r in labels}
    prior_shapes = {shapes[r["file"]] for r in old}
    rng = random.Random(2026100748)
    records = []
    for index, role in enumerate(("development-01", "development-02", "acceptance-01")):
        # SQL positives are scarce; all categories receive at least one of each label.
        extra_eligible = [
            c
            for c in categories
            if all(
                sum(
                    r["category"] == c
                    and r["vulnerable"] == flag
                    and r["file"] not in used
                    for r in labels
                )
                >= (3 - index) + 1
                for flag in (True, False)
            )
        ]
        rng.shuffle(extra_eligible)
        extras = set(extra_eligible[:10])
        assert len(extras) == 10
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
                # Prefer structural groups not exposed, without claiming disjointness if impossible.
                eligible.sort(key=lambda r: shapes[r["file"]] in prior_shapes)
                count = 2 if category in extras else 1
                assert len(eligible) >= count, (role, category, flag)
                selected += eligible[:count]
        rng.shuffle(selected)
        assert len(selected) == 48 and sum(r["vulnerable"] for r in selected) == 24
        used.update(r["file"] for r in selected)
        directory = OUT / "samples" / role
        source = directory / "source"
        for p in SOURCE.rglob("*"):
            if not p.is_file():
                continue
            relative = p.relative_to(SOURCE)
            if (
                relative.parts[0] == "testcode"
                and p.name != "__init__.py"
                and relative.as_posix() not in {r["file"] for r in selected}
            ):
                continue
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)
        for p in source.rglob("*.py"):
            ast.parse(p.read_text())
        assert len(list((source / "testcode").glob("Case*.py"))) == 48
        batches = [
            {
                "group_id": f"batch-{i // 4 + 1:02d}",
                "case_paths": [r["file"] for r in selected[i : i + 4]],
            }
            for i in range(0, 48, 4)
        ]
        save(
            directory / "model-batches.json",
            {"source": str(source), "batches": batches},
        )
        save(
            directory / "evaluator-selection.json",
            {
                "selected": selected,
                "seed": 2026100748,
                "model_batches": batches,
                "role": role,
                "distribution": dict(Counter(r["category"] for r in selected)),
                "structural_prior_overlap_cases": sum(
                    shapes[r["file"]] in prior_shapes for r in selected
                ),
                "shape_groups": {r["file"]: shapes[r["file"]] for r in selected},
                "source_hashes": {
                    str(p.relative_to(source)): sha(p)
                    for p in source.rglob("*")
                    if p.is_file()
                },
            },
        )
        records.append(
            {
                "role": role,
                "case_count": 48,
                "source": str(source),
                "source_files": sum(p.is_file() for p in source.rglob("*")),
                "structural_prior_overlap_cases": sum(
                    shapes[r["file"]] in prior_shapes for r in selected
                ),
            }
        )
        prior_shapes.update(shapes[r["file"]] for r in selected)
    old_config = json.loads(
        (
            ROOT / "artifacts/research/formal/20261005-calibration-v1/config.json"
        ).read_text()
    )
    save(
        OUT / "protocol.json",
        {
            "seed": 2026100748,
            "samples": records,
            "packs": old_config["packs"],
            "codeql_cli": old_config["codeql_cli"],
            "scorer_sha256": sha(ROOT / "scripts/benchmarks/formal_scoring.py"),
            "gold_sha256": sha(GOLD),
            "exact_CWE_mapping": True,
            "concurrency": 3,
            "stage_caps": {"calls": 28, "tokens": 500000, "seconds": 600},
            "max_full_model_executions": 6,
            "planned_executions": [
                "base/development-01",
                "improved/development-01",
                "improved/development-02",
                "optional-next/development-02",
                "base/acceptance-01",
                "final/acceptance-01",
            ],
            "stopping_rule": "Stop after independent acceptance if precision>=CodeQL and F1 exceeds CodeQL and real LLM comparator with lower FP than raw Scout; otherwise report tradeoffs or plateau honestly. No gold-directed retries. Maximum two general production revisions plus bounded repair of infrastructure failures.",
            "unreviewed_never_safe": True,
            "claim": "same-distribution OWASP Python representative engineering evaluation, one run/config; public synthetic and structural overlaps disclosed; not independent project generalization or official scorecard",
            "target_services": False,
            "gui": False,
            "labels_into_model": False,
        },
    )
    print(json.dumps({"samples": records, "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
