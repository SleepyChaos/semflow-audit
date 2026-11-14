"""Algorithm extracted from app.adapters.project_map.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Deterministic source inventory and balanced windows, without security anchors."""
import ast
import hashlib
from collections import defaultdict, deque
from pathlib import Path

from semflow_research.adapters.source_inventory import (
    category,
    inspection_tasks,
    priority,
)


def module_name(file: str) -> str:
    parts = Path(file).parts
    return "/".join(parts[:-1][:2]) or "(root)"


def symbols(text: str, language: str) -> dict:
    if language != "python":
        return {"symbols": [], "imports": [], "limit": "No resolved JS call graph"}
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {"symbols": [], "imports": [], "limit": "Python parse failed"}
    return {
        "symbols": [
            {"name": n.name, "line": n.lineno}
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ][:80],
        "imports": [
            ast.unparse(n)[:250]
            for n in ast.walk(tree)
            if isinstance(n, (ast.Import, ast.ImportFrom))
        ][:40],
        "limit": "Syntactic declarations, not resolved dispatch or business facts",
    }


def build_project_map(
    evidence,
    window_lines: int,
    strategy: str = "balanced",
    *,
    scheduling_profile="full",
) -> dict:
    rows, queues, skipped = ([], defaultdict(deque), [])
    for path in evidence.files():
        file = path.relative_to(evidence.root).as_posix()
        try:
            evidence.allowed(file)
            if path.stat().st_size > 1024 * 1024:
                raise ValueError("file_too_large")
            text = path.read_text()
        except (ValueError, UnicodeError) as exc:
            skipped.append({"file": file, "reason": str(exc)[:200]})
            continue
        lines = text.splitlines()
        module = module_name(file)
        rows.append(
            {
                "file": file,
                "module": module,
                "lines": len(lines),
                **symbols(text, evidence.source_context.language),
                "role_hint": category(file),
            }
        )
        if scheduling_profile == "runtime_first":
            from semflow_research.adapters.scout_scheduling import deferred_reason

            reason = deferred_reason(file)
            if reason:
                skipped.append({"file": file, "reason": reason, "lines": len(lines)})
                continue
        start = 0
        while start < len(lines):
            end = min(start + window_lines, len(lines))
            while end > start + 1 and len("\n".join(lines[start:end])) > 6000:
                end -= 1
            unit = {
                "file": file,
                "module": module,
                "start_line": start + 1,
                "end_line": end,
                "role_hint": category(file),
                "inspection_tasks": inspection_tasks(
                    category(file), semantic=strategy == "business_semantic"
                ),
            }
            if scheduling_profile == "runtime_first":
                from semflow_research.adapters.scout_scheduling import focused_tasks

                unit["inspection_tasks"] = focused_tasks(
                    category(file), strategy == "business_semantic"
                )
            if len(lines[start]) > 12000:
                skipped.append({**unit, "reason": "oversized_source_line"})
            else:
                unit["id"] = hashlib.sha256(
                    f"{evidence.source_context.snapshot_hash}:{file}:{start + 1}:{end}".encode()
                ).hexdigest()[:24]
                queues[file].append(unit)
            start = end
        if not lines:
            skipped.append({"file": file, "reason": "empty_file"})
    modules = defaultdict(list)
    for file in sorted(queues):
        modules[module_name(file)].append(file)
    units = []
    while any(queues.values()):
        rounds = {m: deque(files) for m, files in sorted(modules.items())}
        while any(rounds.values()):
            for files in rounds.values():
                if files:
                    file = files.popleft()
                    if queues[file]:
                        units.append(queues[file].popleft())
    if strategy in {"business_first", "business_semantic"}:
        depth = {}
        counts = defaultdict(int)
        for unit in units:
            depth[unit["id"]] = counts[unit["file"]]
            counts[unit["file"]] += 1
        units.sort(key=lambda u: (priority(u["file"]), depth[u["id"]], u["file"]))
    documents = []
    for name in ("README.md", "pyproject.toml", "package.json", "requirements.txt"):
        path = evidence.root / name
        if path.is_file():
            documents.append(
                {
                    "file": name,
                    "meaning": "Available project document; source read required before treating content as evidence",
                }
            )
    return {
        "scheduling_profile": scheduling_profile,
        "strategy": strategy,
        "snapshot": evidence.source_context.snapshot_hash,
        "language": evidence.source_context.language,
        "files": rows,
        "units": units,
        "skipped": skipped,
        "documents": documents,
        "meaning": "Source window coverage only; no claim of security completeness",
    }


def map_context(project: dict, unit: dict) -> dict:
    related = [r for r in project["files"] if r["module"] == unit["module"]]
    navigation = sorted(
        project["files"], key=lambda r: (priority(r["file"]), r["file"])
    )
    return {
        "navigation": [
            {
                "file": r["file"],
                "lines": r["lines"],
                "role_hint": r.get("role_hint", "source"),
            }
            for r in navigation[:15]
        ],
        "navigation_omitted": max(0, len(navigation) - 15),
        "file_count": len(project["files"]),
        "modules": sorted({r["module"] for r in project["files"]})[:25],
        "nearby_files": [
            {**r, "symbols": r["symbols"][:6], "imports": r["imports"][:4]}
            for r in related[:4]
        ],
        "map_limit": "Partial inventory view; search tools can find other related source",
        "documents": project.get("documents", []),
    }
