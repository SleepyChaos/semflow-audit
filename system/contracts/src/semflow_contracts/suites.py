"""Frozen executable repair assertions, separate from platform review/acceptance."""

from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from semflow_contracts.common import ArtifactRef, Contract, Digest, EntityRef
from semflow_contracts.modelio.verification import VerificationSuite
from semflow_contracts.wire import schema_meaning


class SuiteTargetAlias(Contract):
    previous: EntityRef
    current: EntityRef


class FrozenSuite(Contract):
    # Peers: public.suites.capture / runtime.suite_inputs.read.
    # AGENT: hash covers definition, assertion files, target provenance and exact
    # image. Generated assertions require caller review and do not prove a repair.
    model_config = ConfigDict(json_schema_extra=schema_meaning("repair_suite"))
    schema_version: Literal["semflow.repair-suite/1"] = "semflow.repair-suite/1"
    suite_id: UUID
    snapshot_id: UUID
    source_digest: Digest
    definition: VerificationSuite
    target_refs: tuple[EntityRef, ...] = Field(min_length=1)
    source: Literal["human", "model_generated", "external_fixture"]
    image_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    requirements: str = Field(default="", max_length=4000)
    derived_from: ArtifactRef | None = None
    target_aliases: tuple[SuiteTargetAlias, ...] = ()

    @model_validator(mode="after")
    def exact_targets(self):
        identifiers = [r.entity_id for r in self.target_refs]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Frozen suite targets must be unique")
        security = {
            i
            for c in self.definition.cases
            if c.category == "security"
            for i in c.candidate_ids
        }
        all_ids = {i for c in self.definition.cases for i in c.candidate_ids}
        if security != set(identifiers) or not all_ids.issubset(set(identifiers)):
            raise ValueError(
                "Frozen suite security cases must cover its exact declared targets"
            )
        if bool(self.derived_from) != bool(self.target_aliases):
            raise ValueError(
                "Rebound targets require explicit original definition provenance"
            )
        return self
