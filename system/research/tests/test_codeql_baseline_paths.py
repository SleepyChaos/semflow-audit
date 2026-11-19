import io
import os
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from semflow_research.runtime.baselines import materialize


@pytest.mark.skipif(os.name != "nt", reason="Exercises Windows MAX_PATH during staging")
def test_codeql_baseline_materializes_long_archive_paths_without_os_settings(tmp_path):
    target = tmp_path / "deep-baseline" / "database"
    directory = "db-python/default/cache/cached-strings/tuple-pool/"
    padding = max(64, 268 - len(str(target)) - len(directory))
    member = directory + ("a" * padding)
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("codeql-database.yml", "name: fixture\n")
        archive.writestr(member, b"frozen test database")
    baseline = SimpleNamespace(sarif="sarif", database="db")
    storage = SimpleNamespace(
        read=lambda ref: buffer.getvalue() if ref == "db" else b"{}"
    )
    assert materialize(baseline, artifacts=storage, target=target) == target
    assert (target / "codeql-database.yml").read_text(
        encoding="utf-8"
    ) == "name: fixture\n"
    path = target.joinpath(member)
    long_path = path.with_segments("\\\\?\\" + str(path))
    assert long_path.read_bytes() == b"frozen test database"
