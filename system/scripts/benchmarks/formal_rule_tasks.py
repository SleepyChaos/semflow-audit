"""Freeze bounded OWASP-derived QL tasks, distinct from whole-project discovery."""

import hashlib
import json
import shutil

from scripts.benchmarks.formal_freeze import OUTPUT, save
from scripts.benchmarks.formal_inputs import GOLD, MODEL


def main():
    manifest = OUTPUT / "rule-tasks.json"
    if manifest.exists():
        print("EXISTING_RULE_TASKS=" + str(manifest))
        return
    labels = json.loads((GOLD / "owasp-labels.json").read_text())
    source = MODEL / "owasp-python"
    records, tasks = [], []
    for category, cwe, operation in (
        ("sqli", 89, "SQL execution"),
        ("codeinj", 94, "dynamic code evaluation"),
    ):

        def order(row):
            return hashlib.sha256(("20261005:" + row["task_id"]).encode()).hexdigest()

        positives = sorted(
            [r for r in labels if r["category"] == category and r["vulnerable"]],
            key=order,
        )
        negatives = sorted(
            [r for r in labels if r["category"] == category and not r["vulnerable"]],
            key=order,
        )
        if len(positives) < 3 or len(negatives) < 2:
            raise RuntimeError("Insufficient independently labelled OWASP conditions")
        identifier = "ql-owasp-" + category
        development = MODEL / identifier
        development.mkdir(parents=True, exist_ok=False)
        dev_label = positives[0]
        for variant, rows in (
            ("development", [dev_label]),
            ("hidden", positives[1:3] + negatives[:2]),
        ):
            folder = (
                development
                if variant == "development"
                else GOLD / identifier / "source"
            )
            if variant == "hidden":
                folder.mkdir(parents=True, exist_ok=False)
            shutil.copytree(source / "helpers", folder / "helpers")
            for row in rows:
                target = folder / row["file"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / row["file"], target)
            (folder / "README.md").write_text(
                "# Request handlers\nInspect the actual request processing and helper APIs.\n"
            )
        task = {
            "id": identifier,
            "language": "python",
            "cwe": cwe,
            "source_paths": [dev_label["file"]],
            "requirement": f"Generate a CodeQL vulnerability detector for CWE-{cwe}: externally supplied HTTP request input flows to {operation}. Bind to the actual source and helper APIs, account for sanitization and constant values, and avoid hardcoded filenames, case IDs or lines.",
            "development_label": dev_label,
            "hidden_labels": positives[1:3] + negatives[:2],
            "hidden_source": str(GOLD / identifier / "source"),
            "input_regime": "bounded official testcase plus original helper modules, not full-project discovery",
            "oracle_origin": "official_CWE_boolean_labels; same-generated-family-not-cross-repository",
        }
        tasks.append(task)
        records.append(
            {
                "id": identifier,
                "language": "python",
                "source": str(development),
                "files": sum(p.is_file() for p in development.rglob("*")),
                "input_regime": task["input_regime"],
                "scoring": "QL_testcase_adapter",
                "status": "derived_development_task_not_certified_unseen",
            }
        )
    save(GOLD / "rule-tasks.json", tasks)
    save(OUTPUT / "inputs-derived.json", {"records": records})
    save(
        manifest,
        [
            {
                k: t[k]
                for k in (
                    "id",
                    "language",
                    "source_paths",
                    "requirement",
                    "input_regime",
                    "oracle_origin",
                )
            }
            for t in tasks
        ],
    )
    print(json.dumps([{k: r[k] for k in ("id", "files")} for r in records]))


if __name__ == "__main__":
    main()
