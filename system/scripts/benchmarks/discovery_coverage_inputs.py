"""Add omitted template/config files to a NEW input version; preserve original code."""

import hashlib
import json
import shutil
from pathlib import Path

from app.adapters.snapshot import snapshot_digest
from app.adapters.source_inventory import inspectable

from scripts.benchmarks.formal_freeze import OUTPUT as PREVIOUS
from scripts.benchmarks.formal_freeze import ROOT, save
from scripts.benchmarks.formal_inputs import SKIP


def prepare_inputs(output):
    receipt = output / "inputs.json"
    if receipt.exists():
        rows = json.loads(receipt.read_text())["records"]
        if any(snapshot_digest(Path(r["source"])) != r["snapshot"] for r in rows):
            raise RuntimeError("Expanded input changed")
        return rows
    originals = json.loads((PREVIOUS / "inputs.json").read_text())["records"]
    rows = []
    for project, raw_name in (
        ("rv-flask", "realvuln-damn-vulnerable-flask-application"),
        ("rv-dvna", "realvuln-dvna"),
    ):
        old = next(r for r in originals if r["id"] == project)
        source = Path(old["source"])
        destination = ROOT / "benchmarks/model-inputs" / output.name / project
        if destination.exists():
            raise RuntimeError(
                "Incomplete expanded input retained; explicit recovery needed"
            )
        shutil.copytree(source, destination)
        raw = (
            ROOT
            / "benchmarks/raw/discovery/realvuln/projects"
            / raw_name
            / "source"
        )
        additions = []
        for path in sorted(raw.rglob("*")):
            relative = path.relative_to(raw)
            if (
                not path.is_file()
                or path.is_symlink()
                or any(p in SKIP for p in relative.parts)
                or not inspectable(str(relative), old["language"])
            ):
                continue
            target = destination / relative
            if target.exists():
                continue
            # No new programming-language code or benchmark docs/answers are introduced.
            if path.suffix in {".py", ".js", ".jsx", ".ts", ".tsx"}:
                raise RuntimeError(
                    "Unexpected missing code file; source equivalence review required"
                )
            text = path.read_text()
            if any(
                marker in text.lower()
                for marker in ("cwe-", "cve-", "false positive", "true positive")
            ):
                raise RuntimeError(
                    "New file contains benchmark/security label hints; inspect before model exposure"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
            additions.append(
                {
                    "file": str(relative),
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                }
            )
        unchanged = all(
            (destination / p.relative_to(source)).read_bytes() == p.read_bytes()
            for p in source.rglob("*")
            if p.is_file()
        )
        if not unchanged:
            raise RuntimeError("Existing input changed")
        rows.append(
            {
                **old,
                "source": str(destination),
                "snapshot": snapshot_digest(destination),
                "previous_source": str(source),
                "previous_snapshot": snapshot_digest(source),
                "files": sum(p.is_file() for p in destination.rglob("*")),
                "added_files": additions,
                "existing_files_byte_identical": unchanged,
                "input_regime": "previous sanitized source plus omitted template/config files; no target service execution",
            }
        )
    save(
        receipt,
        {"records": rows, "previous_input_preserved": True, "formal_holdout": False},
    )
    return rows
