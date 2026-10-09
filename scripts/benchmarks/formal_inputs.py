"""Export label-free static inputs; keep original answers and mappings evaluator-only."""

import ast
import csv
import hashlib
import io
import json
import re
import shutil
import tokenize
from pathlib import Path

from app.adapters.source_inventory import CONFIG, TEMPLATES

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "benchmark-data"
OUTPUT = ROOT / "artifacts/research/formal/20261005-calibration-v1"
MODEL = BASE / "model-inputs/20261005-calibration-v1"
GOLD = BASE / "evaluator-only/experiments/20261005-calibration-v1"
ALLOWED = {".py", ".js", ".jsx", ".ts", ".tsx"} | TEMPLATES | CONFIG
SKIP = {".git", "node_modules", "__pycache__", "tests", "test", "results", ".github"}


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def sha(content):
    return hashlib.sha256(content).hexdigest()


def synchronize_case_loader(body):
    """Keep runtime module selection consistent with the anonymized case names."""
    pattern = r"startswith\((['\"])Benchmark\1\)"
    changed, count = re.subn(pattern, "startswith('Case')", body)
    if count != 1:
        raise ValueError(
            "Expected exactly one OWASP module loader; inspect before export"
        )
    ast.parse(changed)
    return changed


def clean_python(body):
    """Blank hint comments, retaining exact line positions for official test mapping."""
    lines = body.splitlines(keepends=True)
    try:
        tokens = tokenize.generate_tokens(io.StringIO(body).readline)
        for token in tokens:
            if token.type == tokenize.COMMENT and re.search(
                r"CWE-\d|CVE-\d|true.positive|false.positive|vulnerab",
                token.string,
                re.IGNORECASE,
            ):
                row, col = token.start
                lines[row - 1] = lines[row - 1][:col] + "\n"
    except tokenize.TokenError:
        raise ValueError("Cannot safely tokenize input") from None
    return "".join(lines)


def export_owasp():
    original = next(
        (BASE / "raw/discovery/owasp-python/source").glob("BenchmarkPython-*")
    )
    destination = MODEL / "owasp-python"
    if destination.exists():
        raise RuntimeError("Refuse to overwrite existing model input")
    mapping = {
        p.stem: "Case" + sha(p.stem.encode())[:12]
        for p in (original / "testcode").glob("BenchmarkTest*.py")
    }
    # Category names in route/template segments disclose labels; consistently alias them.
    segments = {
        part: "group-" + sha(part.encode())[:10]
        for p in (original / "templates/web").glob("*")
        if p.is_dir()
        for part in [p.name]
    }
    pattern = re.compile(
        "|".join(map(re.escape, sorted(mapping, key=len, reverse=True)))
    )
    changes = []
    for path in sorted(original.rglob("*")):
        if not path.is_file() or path.suffix not in ALLOWED:
            continue
        relative = path.relative_to(original)
        if any(part in SKIP or part.startswith(".env") for part in relative.parts):
            continue
        if path.name in {"scoringconfigfile.yaml", "expectedresults-0.1.csv"}:
            continue
        before = path.read_text()
        after = pattern.sub(lambda m: mapping[m.group()], before)
        if relative == Path("app.py"):
            after = synchronize_case_loader(after)
        for segment, replacement in segments.items():
            after = after.replace(segment, replacement)
        renamed = pattern.sub(lambda m: mapping[m.group()], str(relative))
        for segment, replacement in segments.items():
            renamed = renamed.replace(segment, replacement)
        if path.suffix == ".py":
            after = clean_python(after)
            # Validate transformation syntax without importing or executing the app.
            ast.parse(after)
        target = destination / renamed
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(after)
        changes.append(
            {
                "original": str(relative),
                "exported": renamed,
                "before_sha256": sha(before.encode()),
                "after_sha256": sha(after.encode()),
            }
        )
    # Source identity/license notices retained; gold/results and operational scripts omitted.
    shutil.copyfile(original / "LICENSE", destination / "LICENSE")
    (destination / "README.md").write_text(
        "# Request processing application\nStatic analysis input. Runtime services are not started.\n"
    )
    with (original / "expectedresults-0.1.csv").open() as handle:
        rows = list(csv.reader(handle))[1:]
    labels = [
        {
            "task_id": mapping[name],
            "original_id": name,
            "file": f"testcode/{mapping[name]}.py",
            "category": category,
            "vulnerable": value == "true",
            "cwe": int(cwe),
        }
        for name, category, value, cwe in rows
    ]
    save(GOLD / "owasp-labels.json", labels)
    save(GOLD / "owasp-transformations.json", changes)
    return {
        "id": "owasp-python",
        "language": "python",
        "source": str(destination),
        "input_regime": "complete_application_text_no_results_or_score_config",
        "scoring": "official_testcase_CWE_mapping",
        "cases": len(labels),
        "files": len(changes),
        "status": "syntax_checked_not_runtime_equivalence_proven",
    }


def export_project(identifier, source, language):
    destination = MODEL / identifier
    if destination.exists():
        raise RuntimeError("Refuse to overwrite existing model input")
    changes = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if any(part in SKIP or part.startswith(".env") for part in relative.parts):
            continue
        if path.suffix not in ALLOWED and path.name not in {
            "LICENSE",
            "LICENSE.txt",
            "LICENSE.md",
        }:
            continue
        if path.name in {"package-lock.json", "npm-shrinkwrap.json"}:
            continue
        before = path.read_text(errors="strict")
        after = (
            clean_python(before)
            if path.suffix == ".py"
            else re.sub(
                r"(?m)^\s*//[^\n]*(?:CVE-\d|CWE-\d|true.positive|false.positive)[^\n]*$",
                "",
                before,
                flags=re.IGNORECASE,
            )
        )
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(after)
        changes.append(
            {
                "file": str(relative),
                "before_sha256": sha(before.encode()),
                "after_sha256": sha(after.encode()),
            }
        )
    (destination / "README.md").write_text(
        "# Application source\nReview the implementation and normal API contracts.\n"
    )
    save(GOLD / f"{identifier}-transformations.json", changes)
    return {
        "id": identifier,
        "language": language,
        "source": str(destination),
        "files": len(changes),
        "scoring": "root_adjudication_pending",
        "input_regime": "application_text_excludes_tests_docs_and_lockfiles",
        "status": "sanitized_calibration_not_certified_blind",
    }


def main():
    path = OUTPUT / "inputs.json"
    if path.exists():
        print("EXISTING_INPUTS=" + str(path))
        return
    records = [export_owasp()]
    for directory, identifier, language in (
        ("realvuln-damn-vulnerable-flask-application", "rv-flask", "python"),
        ("realvuln-dvna", "rv-dvna", "javascript"),
    ):
        records.append(
            export_project(
                identifier,
                BASE / "raw/discovery/realvuln/projects" / directory / "source",
                language,
            )
        )
    pairs = json.loads((BASE / "raw/project-pairs/manifest.json").read_text())[
        "records"
    ]
    for pair in pairs:
        records.append(
            export_project(
                pair["case_id"],
                BASE / "raw/project-pairs" / pair["case_id"] / "pre",
                pair["language"],
            )
        )
    save(
        path,
        {"records": records, "purpose": "calibration_inputs_not_formal_hidden_split"},
    )
    print(json.dumps([{k: r[k] for k in ("id", "files", "status")} for r in records]))


if __name__ == "__main__":
    main()
