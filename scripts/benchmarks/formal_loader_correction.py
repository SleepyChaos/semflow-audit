"""Correct anonymized module discovery in a new immutable input version."""

import ast
import hashlib
import json
import shutil

from scripts.benchmarks.formal_freeze import OUTPUT, ROOT, save
from scripts.benchmarks.formal_inputs import GOLD, MODEL


def loader_prefix(text):
    values = [
        n.args[0].value
        for n in ast.walk(ast.parse(text))
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "startswith"
        and n.args
        and isinstance(n.args[0], ast.Constant)
        and isinstance(n.args[0].value, str)
    ]
    if len(values) != 1:
        raise ValueError("Ambiguous module loader; inspect manually")
    return values[0]


def main():
    identifier = "owasp-python-loader-fixed"
    directory = (
        ROOT / "benchmark-data/model-inputs/20261005-loader-correction" / identifier
    )
    receipt = OUTPUT / "loader-correction.json"
    if receipt.exists():
        print("EXISTING_LOADER_CORRECTION=" + str(receipt))
        return
    original = next(
        (ROOT / "benchmark-data/raw/discovery/owasp-python/source").glob(
            "BenchmarkPython-*"
        )
    )
    shutil.copytree(MODEL / "owasp-python", directory)
    app = directory / "app.py"
    before = app.read_text()
    assert loader_prefix(before) == "Benchmark"
    after = before.replace("str.startswith('Benchmark')", "str.startswith('Case')")
    assert before != after and loader_prefix(after) == "Case"
    expected = json.loads((GOLD / "owasp-labels.json").read_text())
    before_cases = {
        p.stem
        for p in (directory / "testcode").glob("*.py")
        if p.name.startswith(loader_prefix(before))
    }
    after_cases = {
        p.stem
        for p in (directory / "testcode").glob("*.py")
        if p.name.startswith(loader_prefix(after))
    }
    original_cases = {
        p.stem
        for p in (original / "testcode").glob("*.py")
        if p.name.startswith(loader_prefix((original / "app.py").read_text()))
    }
    assert len(before_cases) == 0
    assert after_cases == {r["task_id"] for r in expected}
    assert original_cases == {r["original_id"] for r in expected}
    app.write_text(after)
    records = json.loads((OUTPUT / "inputs-derived.json").read_text())["records"]
    records.append(
        {
            "id": identifier,
            "language": "python",
            "source": str(directory),
            "files": sum(p.is_file() for p in directory.rglob("*")),
            "input_regime": "full anonymized application text, loader prefix corrected; runtime services not executed",
            "scoring": "official_label_testcase_adapter_not_official_scorecard",
            "status": "loader_case_set_equivalence_checked",
        }
    )
    save(OUTPUT / "inputs-derived.json", {"records": records})
    save(
        receipt,
        {
            "defect": "anonymized IDs not synchronized with dynamic module loader",
            "old_input_preserved": True,
            "old_results_not_primary": True,
            "old_loader_selected_cases": len(before_cases),
            "corrected_loader_selected_cases": len(after_cases),
            "original_loader_selected_cases": len(original_cases),
            "before_app_sha256": hashlib.sha256(before.encode()).hexdigest(),
            "after_app_sha256": hashlib.sha256(after.encode()).hexdigest(),
            "scope": "AST/filename module set invariant, no full runtime equivalence claim",
        },
    )
    print(
        json.dumps(
            {
                "original": len(original_cases),
                "old": len(before_cases),
                "corrected": len(after_cases),
            }
        )
    )


if __name__ == "__main__":
    main()
