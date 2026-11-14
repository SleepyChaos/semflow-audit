"""Verify an installed CodeQL toolchain against its immutable public declaration."""

import yaml
from semflow_contracts.common import relative_path
from semflow_contracts.errors import ResearchError
from semflow_contracts.toolchains import RuleToolchain

from semflow_research.adapters.codeql.scanner import CodeQLScanner
from semflow_research.adapters.snapshot import snapshot_digest


def describe(context):
    configured = (
        context.settings.PYTHON_QUERY_PACK
        if context.spec.language == "python"
        else context.settings.JAVASCRIPT_QUERY_PACK
    )
    name, version = configured.split("@")
    pack = describe_pack(context, name, version)
    lock = context.settings.CODEQL_PACK_PATH / name / version / "codeql-pack.lock.yml"
    dependencies = yaml.safe_load(lock.read_text())["dependencies"]
    return RuleToolchain(
        codeql_version=CodeQLScanner(_kernel=context).version(),
        query_pack=pack,
        libraries=tuple(
            describe_pack(context, n, v["version"])
            for n, v in sorted(dependencies.items())
        ),
        dependencies=dependencies,
    )


def describe_pack(context, name, version):
    from semflow_contracts.discovery import QueryPack

    relative_path(name)
    relative_path(version)
    path = context.settings.CODEQL_PACK_PATH / name / version
    if path.is_symlink() or not (path / "qlpack.yml").is_file():
        raise ResearchError(
            "tool_unavailable", "Frozen CodeQL library source is missing"
        )
    return QueryPack(name=name, version=version, digest=snapshot_digest(path))


def verify(context):
    # WIRE-RECV:research.rule_toolchain — peer: public.toolchains.capture.
    # AGENT: verify the complete lock/source closure and CLI version before any
    # generation or resumed technical check; changing either side needs tests.
    ref = context.spec.inputs.development.query_pack
    if ref.kind != "materials" or ref.schema_version != "semflow.rule-toolchain/1":
        raise ResearchError(
            "invalid_contract", "Expected a typed frozen rule toolchain"
        )
    expected = RuleToolchain.model_validate_json(context.artifacts.read(ref))
    if describe(context) != expected:
        raise ResearchError(
            "integrity_error", "Installed CodeQL toolchain differs from frozen input"
        )
    return expected
