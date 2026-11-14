"""Capture/receive the actual CodeQL DB for downstream algorithms and old views."""

import io
import shutil
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from semflow_contracts.baselines import StaticBaseline
from semflow_contracts.common import relative_path
from semflow_contracts.errors import ResearchError

from semflow_research.adapters.codeql.scanner import CodeQLScanner

MAX_DATABASE_BYTES = 2 * 1024**3


def capture(context, sarif):
    source = context.source_records.get(context.spec.source.snapshot_id)
    stream = io.BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        size = 0
        for path in sorted((context.baseline_directory / "database").rglob("*")):
            if path.is_symlink():
                raise ResearchError(
                    "integrity_error", "Database contains an external symlink"
                )
            if path.is_file():
                size += path.stat().st_size
                if size > MAX_DATABASE_BYTES:
                    raise ResearchError(
                        "resource_exhausted",
                        "Database archive exceeds the supported local transfer size",
                    )
                archive.write(
                    path,
                    path.relative_to(
                        context.baseline_directory / "database"
                    ).as_posix(),
                )
    if not size:
        raise ResearchError("tool_failed", "CodeQL produced an empty database")
    database = context.artifacts.commit(
        stream.getvalue(),
        kind="codeql_database",
        schema_version="codeql.database.zip/1",
        media_type="application/zip",
    )
    # WIRE-SEND:research.baseline — peer: materialize / public.baselines.export.
    # AGENT: retain actual tool version, source identity and SARIF; a database
    # from another scan cannot serve as a frozen original-project baseline.
    return StaticBaseline(
        snapshot_id=context.spec.source.snapshot_id,
        source_digest=context.spec.source.tree_sha256,
        database=database,
        sarif=sarif,
        codeql_version=source.codeql_version,
        query_pack=source.query_pack,
        suite=source.suite,
        original_source_root=str(context.source_root),
        supplemental_rules=getattr(
            getattr(context.spec, "inputs", None), "supplemental_rules", ()
        ),
    )


def materialize(baseline, *, artifacts, target: Path):
    # WIRE-RECV:research.baseline — peer: capture / StaticBaseline declaration.
    # AGENT: archive byte hash, bounded paths and duplicate/symlink rejection
    # must remain paired with the producer; never read a producer's mutable DB.
    artifacts.read(baseline.sarif)
    if target.exists():
        raise ResearchError(
            "execution_conflict", "Baseline target must be a fresh working copy"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with (
            TemporaryDirectory(dir=target.parent) as temporary,
            ZipFile(io.BytesIO(artifacts.read(baseline.database))) as archive,
        ):
            root = Path(temporary) / "database"
            root.mkdir()
            seen, size = set(), 0
            for row in archive.infolist():
                if row.is_dir():
                    continue
                name = relative_path(row.filename)
                size += row.file_size
                if (
                    name in seen
                    or stat.S_ISLNK(row.external_attr >> 16)
                    or size > MAX_DATABASE_BYTES
                ):
                    raise ResearchError(
                        "integrity_error", "Invalid database archive membership or size"
                    )
                seen.add(name)
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(row) as member, path.open("wb") as output:
                    shutil.copyfileobj(member, output)
            if not seen or not (root / "codeql-database.yml").is_file():
                raise ResearchError(
                    "tool_failed", "CodeQL database metadata is missing"
                )
            shutil.move(root, target)
    except (BadZipFile, OSError, ValueError) as exc:
        raise ResearchError(
            "integrity_error", "Cannot materialize frozen CodeQL database"
        ) from exc
    return target


def receive(context, baseline):
    if (
        baseline.snapshot_id != context.spec.source.snapshot_id
        or baseline.source_digest != context.spec.source.tree_sha256
    ):
        raise ResearchError(
            "identity_mismatch", "Static baseline belongs to another source"
        )
    if CodeQLScanner(_kernel=context).version() != baseline.codeql_version:
        raise ResearchError(
            "identity_mismatch", "CodeQL baseline requires its original tool version"
        )
    materialize(
        baseline,
        artifacts=context.artifacts,
        target=context.baseline_directory / "database",
    )
    (context.baseline_directory / "results.sarif").write_bytes(
        context.artifacts.read(baseline.sarif)
    )
    context.source_records.update(
        context.spec.source.snapshot_id,
        query_pack=baseline.query_pack,
        suite=baseline.suite,
        codeql_version=baseline.codeql_version,
    )
    from semflow_research.runtime.rule_inputs import import_rules

    return import_rules(context, baseline.supplemental_rules)
