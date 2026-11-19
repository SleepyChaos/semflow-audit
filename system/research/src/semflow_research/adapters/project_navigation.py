"""Algorithm extracted from app.adapters.project_navigation.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Instance-local navigation index, bound to the immutable snapshot and scope."""
from semflow_research.adapters.local_imports import python_web_entrypoint
from semflow_research.adapters.source_text import read_source_text


def navigation_index(evidence):
    key = (
        "navigation-v1",
        evidence.source_context.snapshot_hash,
        evidence.source_context.language,
        tuple(getattr(evidence, "paths", [])),
    )
    cached = getattr(evidence, "_navigation_index", None)
    if cached and cached[0] == key:
        return cached[1]
    paths = [p.relative_to(evidence.root).as_posix() for p in evidence.files()]
    factories, unreadable = [], []
    if evidence.source_context.language == "python":
        for name in paths:
            if not name.endswith(".py"):
                continue
            path = evidence.allowed(name)
            try:
                if path.stat().st_size > 1024 * 1024:
                    unreadable.append({"file": name, "code": "file_too_large"})
                    continue
                source = read_source_text(path)
            except (OSError, UnicodeError) as exc:
                unreadable.append(
                    {
                        "file": name,
                        "code": "source_unreadable",
                        "reason": str(exc)[:200],
                    }
                )
                continue
            if python_web_entrypoint(source):
                factories.append(name)
    result = {"paths": paths, "python_factories": factories, "unreadable": unreadable}
    evidence._navigation_index = (key, result)
    return result
