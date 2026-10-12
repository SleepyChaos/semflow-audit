"""Evaluator-only preparation; no target imports, model requests or hidden feedback."""

import ast
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT
    / "benchmarks/model-inputs/20261005-loader-correction/owasp-python-loader-fixed"
)
GOLD = (
    ROOT
    / "benchmarks/evaluator-only/experiments/20261005-calibration-v1/owasp-labels.json"
)
OUTPUT = ROOT / "artifacts/research/owasp-discovery/20261007-pilot-preparation"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    labels = json.loads(GOLD.read_text())
    case_files = sorted((SOURCE / "testcode").glob("Case*.py"))
    assert {p.name for p in case_files} == {Path(row["file"]).name for row in labels}
    assert len(labels) == 1230 and sum(l["vulnerable"] for l in labels) == 452
    for p in SOURCE.rglob("*.py"):
        ast.parse(p.read_text())
    app = (SOURCE / "app.py").read_text()
    assert "startswith('Case')" in app and "startswith('Benchmark')" not in app
    assert not GOLD.is_relative_to(SOURCE)
    prohibited = [
        p.relative_to(SOURCE).as_posix()
        for p in SOURCE.rglob("*")
        if p.is_file()
        and (
            p.name.startswith("expectedresults")
            or p.name
            in {"scoringconfigfile.yaml", "ground-truth.json", "owasp-labels.json"}
        )
    ]
    assert not prohibited
    seed = 20261005
    rng = random.Random(seed)
    selected = []
    groups = []
    for category in sorted({l["category"] for l in labels}):
        batch = []
        for flag in [True, False]:
            rows = sorted(
                [
                    l
                    for l in labels
                    if l["category"] == category and l["vulnerable"] == flag
                ],
                key=lambda l: l["task_id"],
            )
            rng.shuffle(rows)
            batch += rows[:2]
        selected += batch
        groups.append(
            {
                "group_id": f"batch-{len(groups) + 1:02d}",
                "case_paths": [l["file"] for l in batch],
            }
        )
    payload = {
        "seed": seed,
        "cases": len(selected),
        "source": str(SOURCE),
        "selected": selected,
        "model_batches": groups,
        "labels_for_evaluator_only": True,
        "input_hashes": {
            str(p.relative_to(SOURCE)): sha(p) for p in SOURCE.rglob("*") if p.is_file()
        },
        "labels_sha256": sha(GOLD),
        "scorer_sha256": sha(ROOT / "system/scripts/benchmarks/formal_scoring.py"),
        "gates": {
            "syntax": True,
            "loader_case_set": 1230,
            "answers_outside_tool_root": True,
            "no_expected_csv_or_gold_in_source": True,
        },
        "known_limits": [
            "Public synthetic benchmark, not certified training-unseen.",
            "Semantic category clues in natural APIs remain; explicit oracle is isolated.",
            "AI representative testcase subset must not be described as full 1230-case discovery.",
            "Exact testcase-CWE adapter, not official scorecard.",
            "No runtime equivalence or exploitation claim; loader checked structurally.",
            "Near-duplicate generated cases are one material family, no hidden generalization claim.",
        ],
        "distribution": dict(Counter(l["category"] for l in selected)),
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    p = OUTPUT / "evaluator-selection.json"
    if p.exists():
        assert json.loads(p.read_text()) == payload
    else:
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    # Separate model-visible selection contains only allowed source paths, no labels/categories.
    p = OUTPUT / "model-batches.json"
    p.write_text(json.dumps({"source": str(SOURCE), "batches": groups}, indent=2))
    print(
        json.dumps(
            {
                "cases": len(selected),
                "positive": sum(l["vulnerable"] for l in selected),
                "groups": len(groups),
                "gates": payload["gates"],
            }
        )
    )


if __name__ == "__main__":
    prepare()
