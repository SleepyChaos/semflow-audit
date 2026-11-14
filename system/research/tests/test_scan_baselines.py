"""A downstream database is an immutable artifact, never the producer workspace."""

import io
from zipfile import ZipFile

import pytest
from discovery_cases import make_scan
from semflow_contracts.errors import ResearchError
from semflow_research.public.baselines import export
from semflow_research.public.discovery import execute
from semflow_research.public.runtime import prepare
from semflow_research.runtime.baselines import materialize, receive


def test_baseline_survives_removal_of_producing_workspace(
    research_case, settings, scanner, tmp_path
):
    import shutil

    spec = make_scan(research_case, settings)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "completed", result.failure
    baseline = result.result.baseline
    shutil.rmtree(context.workspace)
    target = tmp_path / "compatibility"
    export(baseline, root=research_case.ledger.root, target=target)
    assert (target / "database/codeql-database.yml").read_text() == "scripted: true"
    export(baseline, root=research_case.ledger.root, target=target)
    (target / "results.sarif").write_text("{changed}")
    with pytest.raises(ResearchError, match="SARIF differs"):
        export(baseline, root=research_case.ledger.root, target=target)


@pytest.mark.parametrize("name", ["../outside", "/absolute", "duplicate"])
def test_database_archive_rejects_invalid_paths_and_duplicate_members(
    research_case, settings, scanner, tmp_path, name
):
    spec = make_scan(research_case, settings)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "completed", result.failure
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("codeql-database.yml", "test")
        archive.writestr(name, "first")
        if name == "duplicate":
            with pytest.warns(UserWarning, match="Duplicate name"):
                archive.writestr(name, "second")
    ref = context.artifacts.commit(
        stream.getvalue(),
        kind="codeql_database",
        schema_version="codeql.database.zip/1",
    )
    baseline = result.result.baseline.model_copy(update={"database": ref})
    with pytest.raises(ResearchError):
        materialize(baseline, artifacts=context.artifacts, target=tmp_path / "copy")
    assert not (tmp_path / "outside").exists()


def test_baseline_source_identity_is_checked_before_reading_database(
    research_case, settings, scanner
):
    from uuid import uuid4

    spec = make_scan(research_case, settings)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    changed = result.result.baseline.model_copy(update={"snapshot_id": uuid4()})
    with pytest.raises(ResearchError, match="another source"):
        receive(context, changed)
