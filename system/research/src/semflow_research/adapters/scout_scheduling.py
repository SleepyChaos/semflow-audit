"""Algorithm extracted from app.adapters.scout_scheduling.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.

Explicit runtime-focused scope; deferred files are gaps, never safe verdicts."""

from pathlib import Path

from semflow_research.adapters.source_inventory import CONFIG, inspection_tasks


def coverage_order(units, files, window_limit):
    """Schedule a bounded prefix using marginal source and risk coverage."""
    by_file = {row["file"]: row.get("functions", ()) for row in files}
    keys = {}
    for unit in units:
        filename = unit["file"]
        keys[unit["id"]] = (
            {
                (filename, f["start_line"], f["end_line"])
                for f in by_file[filename]
                if unit["start_line"] <= f["end_line"]
                and f["start_line"] <= unit["end_line"]
            },
            set(unit.get("risk", {}).get("reasons", ())),
        )
    remaining = {unit["id"]: unit for unit in units}
    scheduled, covered, families, modules, visited = [], set(), set(), set(), set()

    def score(unit):
        functions, risks = keys[unit["id"]]
        unique_source = min(3, len(functions - covered))
        cost = unit["source_characters"] / 6000
        return (
            2 * unique_source
            + 2 * bool(risks - families)
            + 2 * (unit["module"] not in modules)
            + (unit["file"] not in visited)
            + min(2, unit.get("risk", {}).get("score", 0) / 5)
            - 2 * bool(functions and functions <= covered)
            - cost
        )

    for _ in range(min(len(units), window_limit or 32)):
        unit = max(remaining.values(), key=score)
        identifier = unit["id"]
        functions, risks = keys[identifier]
        covered.update(functions)
        families.update(risks)
        modules.add(unit["module"])
        visited.add(unit["file"])
        scheduled.append(
            {**unit, "selection_reason": "marginal_source_and_risk_coverage"}
        )
        del remaining[identifier]
    return scheduled + list(remaining.values())


def deferred_reason(file):
    path = Path(file.lower())
    parts = set(path.parts[:-1])
    if parts & {"docs", "doc", "examples", "example"}:
        return "deferred_documentation_or_example; readable on demand, not inspected"
    if (
        parts & {"test", "tests", "fixtures", "testdata", "__fixtures__"}
        and path.suffix in CONFIG
    ):
        return "deferred_static_test_data; no safety conclusion"
    return None


def focused_tasks(role, semantic):
    tasks = inspection_tasks(role, semantic=semantic)
    if role == "configuration":
        return [task for task in tasks if task["id"] == "secrets_config"]
    return tasks
