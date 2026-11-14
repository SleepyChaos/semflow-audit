"""Capture an explicitly configured CodeQL closure; never download dependencies."""

from types import SimpleNamespace

from semflow_contracts.common import canonical_bytes

from semflow_research.runtime.artifacts import LocalArtifacts
from semflow_research.runtime.rule_toolchain import describe


def capture(*, root, owner_execution_id, language, settings):
    declaration = describe(
        SimpleNamespace(settings=settings, spec=SimpleNamespace(language=language))
    )
    # WIRE-SEND:research.rule_toolchain — peer: runtime.rule_toolchain.verify.
    # AGENT: preserve actual version and all installed source digests. Capturing
    # resources does not mean that a query compiles or its fixtures pass.
    return LocalArtifacts(root / "artifacts", owner_execution_id).commit(
        canonical_bytes(declaration),
        kind="materials",
        schema_version=declaration.schema_version,
    )
