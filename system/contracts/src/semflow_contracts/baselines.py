"""Immutable CodeQL baseline handed between discovery and technical checks."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from semflow_contracts.common import ArtifactRef, Contract, Digest
from semflow_contracts.rule_values import RuleRef


class StaticBaseline(Contract):
    # Peers: runtime.baselines.capture / materialize and platform scan projection.
    # AGENT: archive contains the actual database; SARIF and source digest bind
    # the same scan. Do not replace a missing database with successful empty output.
    schema_version: Literal["semflow.codeql-baseline/1"] = "semflow.codeql-baseline/1"
    snapshot_id: UUID
    source_digest: Digest
    database: ArtifactRef
    sarif: ArtifactRef
    codeql_version: str = Field(min_length=1)
    query_pack: str = Field(min_length=1)
    suite: str = Field(min_length=1)
    original_source_root: str = Field(min_length=1)
    supplemental_rules: tuple[RuleRef, ...] = ()

    @model_validator(mode="after")
    def artifact_kinds(self):
        if self.database.kind != "codeql_database" or self.sarif.kind != "sarif":
            raise ValueError("Baseline requires database archive and actual SARIF")
        return self
