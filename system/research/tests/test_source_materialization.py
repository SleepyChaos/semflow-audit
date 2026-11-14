import io
import stat
from contextlib import nullcontext
from uuid import uuid4
from zipfile import ZipFile, ZipInfo

import pytest
from semflow_contracts.errors import ResearchError
from semflow_research.adapters.snapshot import snapshot_digest
from semflow_research.runtime.artifacts import LocalArtifacts
from semflow_research.runtime.sources import capture, materialize


def test_canonical_tree_order_and_logical_utf8_excerpt(tmp_path):
    root = tmp_path / "input"
    (root / "a").mkdir(parents=True)
    (root / "a/nested.py").write_text("value = 1\n")
    (root / "a.py").write_bytes(("变量" * 2500 + "\r\n").encode())
    identifier = uuid4()
    artifacts = LocalArtifacts(tmp_path / "artifacts", identifier)
    snapshot = capture(root, artifacts=artifacts, languages=("python",))
    assert snapshot.tree_sha256 == snapshot_digest(root)
    reader = materialize(
        snapshot,
        artifacts=artifacts,
        execution_id=identifier,
        target=tmp_path / "frozen",
    )
    evidence = reader.read("a.py", 1, 1)
    assert artifacts.read(evidence.content) == ("变量" * 2500).encode()
    reader.validate(evidence)
    assert (tmp_path / "frozen/a.py").read_bytes().endswith(b"\r\n")


@pytest.mark.parametrize(
    "entry", ["../outside.py", "app.py", "foreign.py", "symlink.py"]
)
def test_archive_cannot_override_manifest_or_escape_snapshot(
    research_case, tmp_path, entry
):
    case = research_case
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("app.py", b"value = eval(input())\n")
        info = ZipInfo(entry)
        if entry == "symlink.py":
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with pytest.warns(UserWarning) if entry == "app.py" else nullcontext():
            archive.writestr(info, b"forged")
    archive_ref = case.artifacts.commit(
        stream.getvalue(), kind="source_archive", schema_version="source.zip/1"
    )
    snapshot = case.snapshot.model_copy(update={"archive": archive_ref})
    with pytest.raises(ResearchError):
        materialize(
            snapshot,
            artifacts=case.artifacts,
            execution_id=case.execution_id,
            target=tmp_path / "rejected",
        )
    assert (
        not (tmp_path / "rejected").exists() and not (tmp_path / "outside.py").exists()
    )


def test_existing_materialization_is_checked_instead_of_overwritten(
    research_case, tmp_path
):
    case = research_case
    target = tmp_path / "frozen"
    materialize(
        case.snapshot,
        artifacts=case.artifacts,
        execution_id=case.execution_id,
        target=target,
    )
    (target / "app.py").write_text("tampered")
    with pytest.raises(ResearchError, match="bytes changed"):
        materialize(
            case.snapshot,
            artifacts=case.artifacts,
            execution_id=case.execution_id,
            target=target,
        )
    assert (target / "app.py").read_text() == "tampered"
