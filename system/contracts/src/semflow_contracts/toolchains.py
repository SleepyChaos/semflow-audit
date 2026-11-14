"""Exact installed CodeQL source closure used by rule compilation and execution."""

from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from semflow_contracts.common import Contract
from semflow_contracts.discovery import QueryPack
from semflow_contracts.wire import schema_meaning


class DependencyPin(Contract):
    version: str = Field(min_length=1)


class RuleToolchain(Contract):
    # Peers: public.toolchains.capture -> runtime.rule_toolchain.verify.
    # AGENT: query pack, every transitive library's bytes, lock and actual CLI
    # version are one identity. Do not reduce this to a resource profile name.
    model_config = ConfigDict(json_schema_extra=schema_meaning("rule_toolchain"))
    schema_version: Literal["semflow.rule-toolchain/1"] = "semflow.rule-toolchain/1"
    codeql_version: str = Field(min_length=1)
    query_pack: QueryPack
    libraries: tuple[QueryPack, ...] = Field(min_length=1)
    dependencies: dict[str, DependencyPin]

    @model_validator(mode="after")
    def complete_closure(self):
        names = [library.name for library in self.libraries]
        if len(set(names)) != len(names) or set(names) != set(self.dependencies):
            raise ValueError("Toolchain must bind exactly every locked library")
        if any(self.dependencies[p.name].version != p.version for p in self.libraries):
            raise ValueError("Library versions must equal the frozen dependency lock")
        return self
