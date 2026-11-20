"""Content-addressed source capture and manifest-checked archive materialization."""

import hashlib
import io
import shutil
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from semflow_contracts.common import (
    SourceFile,
    SourceManifest,
    SourceSnapshot,
    canonical_bytes,
    digest,
    relative_path,
)
from semflow_contracts.errors import ResearchError

from semflow_research.adapters.snapshot import is_link
from semflow_research.runtime.evidence import SnapshotReader

MAX_SOURCE_BYTES = 256 * 1024 * 1024
MAX_SOURCE_FILES = 20000


def capture(
    root: Path, *, artifacts, languages, origin=None, archive_kind="source_archive"
) -> SourceSnapshot:
    if is_link(root) or not root.is_dir():
        raise ResearchError(
            "invalid_contract",
            "Source capture requires a directory without symlinks or junctions",
        )
    files, total = [], 0
    stream = io.BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        for path in sorted(
            root.rglob("*"), key=lambda path: path.relative_to(root).as_posix()
        ):
            if is_link(path):
                raise ResearchError(
                    "integrity_error", "Source capture refuses symlinks and junctions"
                )
            if not path.is_file():
                continue
            name = relative_path(path.relative_to(root).as_posix())
            size = path.stat().st_size
            total += size
            if total > MAX_SOURCE_BYTES or len(files) >= MAX_SOURCE_FILES:
                raise ResearchError(
                    "invalid_contract", "Source capture exceeds the supported size"
                )
            content = path.read_bytes()
            if len(content) != size:
                raise ResearchError(
                    "integrity_error", "Source changed while being captured"
                )
            files.append(
                SourceFile(
                    path=name,
                    sha256=hashlib.sha256(content).hexdigest(),
                    size_bytes=len(content),
                )
            )
            # Fixed archive metadata avoids implicit timestamps changing identity.
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    manifest = SourceManifest(files=tuple(files))
    manifest_ref = artifacts.commit(
        canonical_bytes(manifest),
        kind="source_manifest",
        schema_version=manifest.schema_version,
    )
    archive_ref = artifacts.commit(
        stream.getvalue(),
        kind=archive_kind,
        schema_version="source.zip/1",
        media_type="application/zip",
    )
    # WIRE-SEND:research.source — peer: materialize / SnapshotReader.
    # AGENT: source identity is the canonical manifest digest; change the receiving
    # archive/byte checks and any explicit platform legacy-hash conversion together.
    return SourceSnapshot(
        snapshot_id=uuid4(),
        tree_sha256=digest(manifest),
        archive=archive_ref,
        manifest=manifest_ref,
        languages=languages,
        origin=origin or {"kind": "directory"},
    )


def materialize(
    snapshot: SourceSnapshot, *, artifacts, execution_id, target: Path
) -> SnapshotReader:
    # WIRE-RECV:research.source — peer: capture; the tree digest hashes the
    # canonical SourceManifest, not the platform's legacy path-NUL-digest format.
    # AGENT: preserve both byte validation and hash-algorithm identity at the sender.
    manifest = SourceManifest.model_validate_json(artifacts.read(snapshot.manifest))
    if digest(manifest) != snapshot.tree_sha256:
        raise ResearchError("integrity_error", "Source manifest identity changed")
    if target.exists():
        return SnapshotReader(target, snapshot, execution_id, artifacts)
    target.parent.mkdir(parents=True, exist_ok=True)
    expected = {entry.path: entry for entry in manifest.files}
    total = sum(entry.size_bytes for entry in manifest.files)
    if total > MAX_SOURCE_BYTES or len(expected) > MAX_SOURCE_FILES:
        raise ResearchError(
            "invalid_contract", "Source manifest exceeds the supported size"
        )
    try:
        with (
            TemporaryDirectory(dir=target.parent) as temporary,
            ZipFile(io.BytesIO(artifacts.read(snapshot.archive))) as archive,
        ):
            root, observed = Path(temporary) / "source", set()
            root.mkdir()
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                name = relative_path(entry.filename)
                if (
                    name in observed
                    or name not in expected
                    or stat.S_ISLNK(entry.external_attr >> 16)
                ):
                    raise ResearchError(
                        "integrity_error",
                        "Source archive has duplicate, foreign or symlink entries",
                    )
                frozen = expected[name]
                if entry.file_size != frozen.size_bytes:
                    raise ResearchError(
                        "integrity_error",
                        "Archive file size differs from the source manifest",
                    )
                with archive.open(entry) as member:
                    data = member.read(frozen.size_bytes + 1)
                if (
                    len(data) != frozen.size_bytes
                    or hashlib.sha256(data).hexdigest() != frozen.sha256
                ):
                    raise ResearchError(
                        "integrity_error",
                        "Archive bytes differ from the source manifest",
                    )
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                observed.add(name)
            if observed != set(expected):
                raise ResearchError(
                    "integrity_error", "Source archive omits frozen files"
                )
            SnapshotReader(root, snapshot, execution_id, artifacts)
            # The caller holds the exclusive execution claim before materializing.
            shutil.move(root, target)
    except (BadZipFile, ValueError, OSError) as exc:
        raise ResearchError(
            "integrity_error", "Cannot materialize the frozen source archive"
        ) from exc
    return SnapshotReader(target, snapshot, execution_id, artifacts)
