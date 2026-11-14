"""Deliver immutable scan artifacts into an explicitly selected compatibility view."""

from pathlib import Path

from semflow_research.runtime.artifacts import LocalArtifacts
from semflow_research.runtime.baselines import materialize


def for_execution(execution_id, *, root):
    """Select the original scan retained by a published discovery or its review."""
    from semflow_contracts.errors import ResearchError

    from semflow_research.public.runs import inspect, specification

    result = inspect(execution_id, root=root)
    spec = specification(execution_id, root=root)
    if result is None or result.module != "discovery" or result.result is None:
        raise ResearchError(
            "invalid_contract", "Baseline selection needs published discovery"
        )
    # Interface peers: discovery_requests / repair_requests / rule_requests ->
    # runtime.baselines.receive. AGENT: review output may carry no new scan;
    # retain its explicit immutable input baseline, never recapture a workspace
    # or derive a different baseline from current tool defaults.
    baseline = result.result.baseline or getattr(spec.inputs, "baseline", None)
    if baseline is not None and (
        baseline.snapshot_id != spec.source.snapshot_id
        or baseline.source_digest != spec.source.tree_sha256
    ):
        raise ResearchError(
            "identity_mismatch", "Upstream baseline belongs to another source"
        )
    return baseline


def export(baseline, *, root, target: Path):
    store = LocalArtifacts(
        root / "artifacts",
        baseline.database.owner_execution_id,
        upstream=(baseline.sarif,),
    )
    import io
    from zipfile import ZipFile

    from semflow_contracts.common import canonical_bytes
    from semflow_contracts.errors import ResearchError

    pointer = target / "research-baseline.json"
    if any(
        path.is_symlink()
        for path in (target, pointer, target / "database", target / "results.sarif")
    ):
        raise ResearchError(
            "integrity_error", "Compatibility baseline cannot contain path symlinks"
        )
    if pointer.exists():
        if pointer.read_bytes() != canonical_bytes(baseline):
            raise ResearchError(
                "integrity_error", "Compatibility baseline identity changed"
            )
        if not (target / "results.sarif").is_file() or (
            target / "results.sarif"
        ).read_bytes() != store.read(baseline.sarif):
            raise ResearchError(
                "integrity_error", "Compatibility SARIF differs from its frozen receipt"
            )
        return
    if (target / "database").exists():
        with ZipFile(io.BytesIO(store.read(baseline.database))) as archive:
            for row in archive.infolist():
                if row.is_dir():
                    continue
                from semflow_contracts.common import relative_path

                path = target / "database" / relative_path(row.filename)
                if (
                    not path.is_file()
                    or path.is_symlink()
                    or path.read_bytes() != archive.read(row)
                ):
                    raise ResearchError(
                        "integrity_error",
                        "Uncommitted compatibility database differs from the frozen scan",
                    )
    else:
        materialize(baseline, artifacts=store, target=target / "database")
    (target / "results.sarif").write_bytes(store.read(baseline.sarif))
    pointer.write_bytes(canonical_bytes(baseline))


def findings(baseline, *, root, legacy_source_digest):
    """Explicit projection to the old SARIF parser's hash namespace and locations."""
    import tempfile

    from semflow_research.adapters.codeql.sarif import parse_sarif

    store = LocalArtifacts(root / "artifacts", baseline.sarif.owner_execution_id)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "results.sarif"
        path.write_bytes(store.read(baseline.sarif))
        rows = parse_sarif(path, legacy_source_digest)
    for row in rows:
        for point in [
            *row["locations"],
            *[p for flow in row["code_flows"] for p in flow],
        ]:
            if Path(point["file"]).is_absolute():
                point["file"] = (
                    Path(point["file"])
                    .relative_to(baseline.original_source_root)
                    .as_posix()
                )
    return rows


def capture(
    *,
    snapshot,
    source_root,
    directory,
    root,
    execution_id,
    codeql_version,
    query_pack,
    suite,
):
    """Freeze an existing verified scan for a new independent downstream request."""
    from types import SimpleNamespace

    from semflow_research.runtime.baselines import capture as freeze

    store = LocalArtifacts(root / "artifacts", execution_id)
    sarif = store.commit(
        (directory / "results.sarif").read_bytes(),
        kind="sarif",
        schema_version="sarif/2.1.0",
    )
    source = SimpleNamespace(
        codeql_version=codeql_version, query_pack=query_pack, suite=suite
    )
    context = SimpleNamespace(
        spec=SimpleNamespace(source=snapshot),
        artifacts=store,
        source_root=source_root,
        baseline_directory=directory,
        source_records=SimpleNamespace(get=lambda identifier: source),
    )
    return freeze(context, sarif)


def input_findings(
    baseline, *, snapshot, source_root, root, execution_id, legacy_source_digest
):
    """Explicit source-ID conversion for caller input codecs; no platform state."""
    from types import SimpleNamespace

    from semflow_contracts.bundles import StaticFindingBundle

    from semflow_research.runtime.discovery_outputs import export_static
    from semflow_research.runtime.evidence import SnapshotReader

    store = LocalArtifacts(
        root / "artifacts", execution_id, upstream=(baseline.sarif, snapshot.manifest)
    )
    reader = SnapshotReader(source_root, snapshot, execution_id, store)
    canonical = findings(baseline, root=root, legacy_source_digest=snapshot.tree_sha256)
    legacy = findings(baseline, root=root, legacy_source_digest=legacy_source_digest)
    context = SimpleNamespace(
        artifacts=store,
        execution_id=execution_id,
        spec=SimpleNamespace(source=snapshot),
        source=reader,
    )
    reference = export_static(context, canonical, baseline.sarif)
    bundle = StaticFindingBundle.model_validate_json(store.read(reference))
    # Peer: research_bridge.repair_baseline.freeze -> repair_inputs.freeze_targets.
    # AGENT: both ID algorithms hash different source namespaces; retain an
    # explicit verified mapping, never reuse the legacy hexadecimal ID as a UUID.
    return reference, {
        old["id"]: record for old, record in zip(legacy, bundle.records, strict=True)
    }
