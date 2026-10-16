"""Instance-local navigation index, bound to the immutable snapshot and scope."""

from app.adapters.local_imports import python_web_entrypoint


def navigation_index(evidence):
    key = (
        "navigation-v1",
        evidence.audit.snapshot_hash,
        evidence.audit.language,
        tuple(getattr(evidence, "paths", [])),
    )
    cached = getattr(evidence, "_navigation_index", None)
    if cached and cached[0] == key:
        return cached[1]
    paths = [p.relative_to(evidence.root).as_posix() for p in evidence.files()]
    factories = []
    if evidence.audit.language == "python":
        for name in paths:
            if name.endswith(".py") and python_web_entrypoint(
                evidence.allowed(name).read_text()
            ):
                factories.append(name)
    result = {"paths": paths, "python_factories": factories}
    evidence._navigation_index = (key, result)
    return result
