import sys
from uuid import uuid4

import pytest
from semflow_contracts.errors import ResearchError
from semflow_research.runtime.artifacts import LocalArtifacts


def test_real_code_evidence_has_verified_source_and_byte_identity(research_case):
    case = research_case
    evidence = case.reader.read("app.py", 1, 1)
    assert case.artifacts.read(evidence.content) == b"value = eval(input())"
    assert evidence.snapshot_id == case.snapshot.snapshot_id
    assert evidence.location.file_sha256 == case.reader.files["app.py"].sha256
    case.reader.validate(evidence)


def test_valid_schema_with_invented_evidence_bytes_is_rejected(research_case):
    case = research_case
    actual = case.reader.read("app.py", 1, 1)
    invented = case.artifacts.commit(
        b"Invented source text",
        kind="source_slice",
        schema_version="test/1",
        media_type="text/plain",
    )
    forged = actual.model_copy(update={"content": invented, "digest": invented.sha256})
    with pytest.raises(ResearchError, match="cited source bytes"):
        case.reader.validate(forged)
    with pytest.raises(ResearchError, match="this snapshot"):
        case.reader.validate(
            actual.model_copy(
                update={"snapshot_id": uuid4(), "location": None, "kind": "knowledge"}
            )
        )


def test_source_change_extra_file_and_traversal_never_produce_evidence(research_case):
    case = research_case
    with pytest.raises(ResearchError, match="outside the snapshot"):
        case.reader.read("../outside.py", 1, 1)
    (case.source / "unfrozen.py").write_text("print('extra')")
    with pytest.raises(ResearchError, match="not frozen"):
        case.reader.read("app.py", 1, 1)
    (case.source / "unfrozen.py").unlink()
    (case.source / "app.py").write_text("print('changed')")
    with pytest.raises(ResearchError, match="changed"):
        case.reader.read("app.py", 1, 1)


def test_cross_execution_artifacts_require_exact_explicit_upstream(research_case):
    case = research_case
    ref = case.artifacts.commit(b"original", kind="log", schema_version="test/1")
    other_id = uuid4()
    unauthorized = LocalArtifacts(case.artifacts.root, other_id)
    with pytest.raises(ResearchError, match="explicit upstream"):
        unauthorized.read(ref)
    authorized = LocalArtifacts(case.artifacts.root, other_id, upstream=(ref,))
    assert authorized.read(ref) == b"original"
    with pytest.raises(ResearchError, match="explicit upstream"):
        authorized.read(ref.model_copy(update={"artifact_id": uuid4()}))


def test_artifact_tampering_is_detected_and_never_overwritten(research_case):
    case = research_case
    ref = case.artifacts.commit(b"original", kind="patch", schema_version="test/1")
    path = case.artifacts.root / str(case.execution_id) / ref.path
    path.write_bytes(b"modified")
    with pytest.raises(ResearchError, match="Artifact bytes"):
        case.artifacts.read(ref)
    with pytest.raises(ResearchError, match="Artifact bytes"):
        case.artifacts.commit(b"original", kind="patch", schema_version="test/1")
    assert path.read_bytes() == b"modified"


def test_symlink_source_and_artifact_escape_are_rejected(research_case, tmp_path):
    case = research_case
    ref = case.artifacts.commit(b"original", kind="log", schema_version="test/1")
    path = case.artifacts.root / str(case.execution_id) / ref.path
    outside = tmp_path / "outside"
    outside.write_bytes(b"original")
    path.unlink()
    try:
        path.symlink_to(outside)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows principal cannot create symbolic links")
        raise
    with pytest.raises(ResearchError, match="escaped"):
        case.artifacts.read(ref)
    (case.source / "link.py").symlink_to(case.source / "app.py")
    with pytest.raises(ResearchError, match="symlink"):
        case.reader.read("app.py", 1, 1)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows directory junction")
def test_unprivileged_directory_junction_cannot_enter_snapshot_or_artifacts(
    research_case, tmp_path
):
    from _winapi import CreateJunction

    from semflow_research.adapters.snapshot import snapshot_digest
    from semflow_research.domain.errors import AuditError
    from semflow_research.evidence.evidence import EvidenceService
    from semflow_research.runtime.sources import capture

    case = research_case
    empty = tmp_path / "disposable-empty"
    empty.mkdir()
    junction = case.source / "junction"
    CreateJunction(str(empty), str(junction))
    assert junction.is_junction()
    try:
        with pytest.raises(ResearchError, match="junction"):
            capture(case.source, artifacts=case.artifacts, languages=("python",))
        with pytest.raises(ResearchError, match="junction"):
            case.reader.verify_snapshot()
        with pytest.raises(AuditError, match="链接"):
            snapshot_digest(case.source)
        source = object.__new__(EvidenceService)
        source.root = case.source.resolve()
        with pytest.raises(AuditError, match="链接"):
            source.target("junction")
    finally:
        junction.rmdir()

    alias = tmp_path / "artifact-root-junction"
    CreateJunction(str(empty), str(alias))
    assert alias.is_junction()
    try:
        with pytest.raises(ResearchError, match="junction"):
            LocalArtifacts(alias, uuid4())
    finally:
        alias.rmdir()
