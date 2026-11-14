"""Immutable values and content identities shared by the three kernels."""

import hashlib
import json
from pathlib import PurePosixPath
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from semflow_contracts.wire import schema_meaning

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Language = Literal["python", "javascript"]
RulePurpose = Literal["review_anchor", "vulnerability_detector", "framework_model"]


def relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or path.as_posix() != value
        or any(part in {".", ".."} for part in path.parts)
        or value == "."
        or any(character in value for character in ("\\", ":", "\x00"))
    ):
        raise ValueError("Expected a normalized, relative POSIX path")
    return value


RelativePath = Annotated[str, AfterValidator(relative_path)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


def canonical_bytes(value: BaseModel | dict | list) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=False)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest(value: BaseModel | dict | list) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


ArtifactKind = Literal[
    "source_archive",
    "source_manifest",
    "evidence_bundle",
    "candidate_bundle",
    "decision_bundle",
    "sarif",
    "codeql_database",
    "patch",
    "patched_source",
    "repair_attempts",
    "suite",
    "validation_receipt",
    "query",
    "rule_modules",
    "corpus_manifest",
    "retrieval_trace",
    "model_call",
    "log",
    "checkpoint",
    "result_bundle",
    "result_manifest",
    "source_slice",
    "prompt",
    "dependencies",
    "materials",
    "coverage",
    "rule_fixtures",
    "run_spec",
]


class ArtifactRef(Contract):
    artifact_id: UUID
    owner_execution_id: UUID
    kind: ArtifactKind
    schema_version: str = Field(min_length=1)
    path: RelativePath
    sha256: Digest
    size_bytes: int = Field(ge=0)
    media_type: str = Field(min_length=1)


class BundleRef(Contract):
    artifact: ArtifactRef
    entity_ids: tuple[UUID, ...] | None = None

    @model_validator(mode="after")
    def unique_selection(self):
        if self.entity_ids is not None and len(set(self.entity_ids)) != len(
            self.entity_ids
        ):
            raise ValueError("Bundle selection cannot repeat an entity ID")
        return self


class EntityRef(Contract):
    execution_id: UUID
    entity_id: UUID
    bundle: ArtifactRef

    @model_validator(mode="after")
    def bundle_owner(self):
        if self.execution_id != self.bundle.owner_execution_id:
            raise ValueError("Entity bundle belongs to a different execution")
        return self


class SourceOrigin(Contract):
    kind: Literal["archive", "git", "directory"]
    revision: str | None = None
    label: str | None = None


class SourceSnapshot(Contract):
    snapshot_id: UUID
    tree_sha256: Digest
    archive: ArtifactRef
    manifest: ArtifactRef
    languages: tuple[Language, ...] = Field(min_length=1)
    origin: SourceOrigin

    @model_validator(mode="after")
    def source_artifacts(self):
        if (
            self.archive.kind not in {"source_archive", "patched_source"}
            or self.manifest.kind != "source_manifest"
        ):
            raise ValueError("Source snapshot requires an archive and source manifest")
        if len(set(self.languages)) != len(self.languages):
            raise ValueError("Duplicate source language")
        return self


class SourceLocation(Contract):
    snapshot_id: UUID
    path: RelativePath
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    file_sha256: Digest
    # Peers: discovery_outputs.location / bundle_io.import_targets / bridge review inputs.
    # AGENT: retain optional SARIF columns as navigation metadata; line evidence
    # still requires actual source-byte validation. Missing columns are unknown.
    start_column: int | None = Field(default=None, ge=1)
    end_column: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def ordered_range(self):
        if self.end_line < self.start_line:
            raise ValueError("Source range ends before it starts")
        return self


class SourceFile(Contract):
    path: RelativePath
    sha256: Digest
    size_bytes: int = Field(ge=0)


class SourceManifest(Contract):
    # Interface peers: runtime.sources.capture / materialize and SnapshotReader.
    # AGENT: keep canonical path ordering, file-byte digests and the tree hash
    # algorithm identical at both ends; never reinterpret another digest format.
    model_config = ConfigDict(json_schema_extra=schema_meaning("source"))

    schema_version: Literal["semflow.source-tree/1"] = "semflow.source-tree/1"
    files: tuple[SourceFile, ...]

    @model_validator(mode="after")
    def canonical_paths(self):
        paths = [entry.path for entry in self.files]
        if paths != sorted(set(paths)):
            raise ValueError("Source manifest paths must be unique and sorted")
        return self
