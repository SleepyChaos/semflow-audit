"""Verify the explicitly frozen scan controls against installed query bytes."""

import hashlib

from semflow_contracts.common import relative_path
from semflow_contracts.errors import ResearchError

from semflow_research.adapters.snapshot import snapshot_digest


def validate_scan(context, inputs):
    if inputs.build_profile != "none":
        raise ResearchError(
            "unsupported_operation",
            "CodeQL adapter currently supports the explicit none build profile",
        )
    relative_path(inputs.query_pack.name)
    relative_path(inputs.query_pack.version)
    relative_path(inputs.suite.name)
    pack = (
        context.settings.CODEQL_PACK_PATH
        / inputs.query_pack.name
        / inputs.query_pack.version
    )
    suite = pack / inputs.suite.name
    if (
        pack.is_symlink()
        or suite.is_symlink()
        or not pack.is_dir()
        or not suite.is_file()
    ):
        raise ResearchError(
            "tool_unavailable", "Frozen CodeQL query pack is not installed"
        )
    if (
        snapshot_digest(pack) != inputs.query_pack.digest
        or hashlib.sha256(suite.read_bytes()).hexdigest() != inputs.suite.digest
    ):
        raise ResearchError(
            "integrity_error",
            "Installed CodeQL query pack or suite differs from the frozen request",
        )
