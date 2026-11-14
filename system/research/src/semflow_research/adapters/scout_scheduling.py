"""Algorithm extracted from app.adapters.scout_scheduling.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Explicit runtime-focused scope; deferred files are gaps, never safe verdicts."""
from pathlib import Path

from semflow_research.adapters.source_inventory import CONFIG, inspection_tasks


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
