"""Receive the original scan into a verified immutable baseline working namespace."""

import io
from pathlib import Path
from zipfile import ZipFile

from semflow_contracts.common import canonical_bytes, relative_path
from semflow_contracts.errors import ResearchError

from semflow_research.adapters.codeql.sarif import parse_sarif
from semflow_research.adapters.codeql.scanner import CodeQLScanner
from semflow_research.runtime.baselines import materialize
from semflow_research.runtime.rule_inputs import import_rules


def receive(context, baseline):
    # WIRE-RECV:research.baseline — peer: platform baseline freezer / StaticBaseline.
    # AGENT: source prefix belongs to the original DB; verify archived bytes
    # against relocated source, never rewrite it to make coverage appear valid.
    if (
        baseline.snapshot_id != context.spec.source.snapshot_id
        or baseline.source_digest != context.spec.source.tree_sha256
    ):
        raise ResearchError(
            "identity_mismatch", "Rule baseline belongs to another source"
        )
    if CodeQLScanner(_kernel=context).version() != baseline.codeql_version:
        raise ResearchError(
            "identity_mismatch", "Rule replay requires its original CodeQL version"
        )
    base = context.baseline_directory
    database = base / "database"
    pointer = base / "frozen-baseline.json"
    if database.exists():
        if (
            pointer.is_symlink()
            or not pointer.is_file()
            or pointer.read_bytes() != canonical_bytes(baseline)
        ):
            raise ResearchError("integrity_error", "Rule baseline identity changed")
        with ZipFile(io.BytesIO(context.artifacts.read(baseline.database))) as archive:
            expected = {}
            for member in archive.infolist():
                if not member.is_dir():
                    name = relative_path(member.filename)
                    expected[name] = archive.read(member)
            actual = {
                path.relative_to(database).as_posix(): path
                for path in database.rglob("*")
                if path.is_file()
            }
            if set(actual) != set(expected) or any(
                path.is_symlink() or path.read_bytes() != expected[name]
                for name, path in actual.items()
            ):
                raise ResearchError(
                    "integrity_error", "Original rule baseline database bytes changed"
                )
    else:
        materialize(baseline, artifacts=context.artifacts, target=database)
        pointer.write_bytes(canonical_bytes(baseline))
    sarif = context.artifacts.read(baseline.sarif)
    (base / "results.sarif").write_bytes(sarif)
    try:
        findings = parse_sarif(base / "results.sarif", baseline.source_digest)
    except Exception as error:
        raise ResearchError(
            "parse_failed",
            "Original rule baseline SARIF is invalid",
            detail=baseline.sarif,
        ) from error
    for finding in findings:
        for point in [
            *finding["locations"],
            *[p for flow in finding["code_flows"] for p in flow],
        ]:
            name = point["file"]
            if Path(name).is_absolute():
                try:
                    name = (
                        Path(name).relative_to(baseline.original_source_root).as_posix()
                    )
                except ValueError as error:
                    raise ResearchError(
                        "evidence_invalid",
                        "Baseline finding lies outside original source",
                    ) from error
            context.source._slice(name, point["line"], point["end_line"])
            point["file"] = name
    context.source_records.update(
        context.spec.source.snapshot_id,
        findings=findings,
        codeql_version=baseline.codeql_version,
        query_pack=baseline.query_pack,
        suite=baseline.suite,
    )
    return import_rules(context, baseline.supplemental_rules)
