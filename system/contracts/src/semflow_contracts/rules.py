"""Rule generation inputs separate development feedback from hidden evaluation."""

from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from semflow_contracts.actions import ApprovalDecision
from semflow_contracts.baselines import StaticBaseline
from semflow_contracts.common import (
    ArtifactRef,
    Contract,
    Digest,
    EntityRef,
    RelativePath,
    RulePurpose,
)
from semflow_contracts.evidence import TargetBundle
from semflow_contracts.rule_values import CorpusSnapshot, RuleRef
from semflow_contracts.validation import ValidationReceipt
from semflow_contracts.wire import schema_meaning


class RetrievalPolicy(Contract):
    mode: Literal["bm25", "vector", "hybrid"]
    collection_routing: bool
    corpus_document_ids: tuple[UUID, ...] | None = None
    # Interface peer: adapters.retrieval.knowledge.KnowledgeRetriever.retrieve.
    # AGENT: this caps each role lookup, not the union of independently routed roles.
    top_k: int = Field(
        ge=1,
        description="Per-role lookup limit; explicit role quotas are combined and deduplicated afterwards.",
    )
    version: str = Field(min_length=1)


class RuleMethodPolicy(Contract):
    version: str = Field(min_length=1)
    full_feedback: bool
    generation_constraint: bool
    progress_feedback: bool
    compact_context: bool
    source_preparation_context: bool
    rag_before_inspection: bool


class DevelopmentPlan(Contract):
    compile: bool
    development_fixtures: ArtifactRef | None = None
    project_replay: bool
    # Peer: rule_operations.prepare_inputs -> rule_project_validation.replay_project.
    # AGENT: replay uses the actual original database/SARIF/source prefix; never
    # rebuild a different baseline or turn missing resources into zero findings.
    static_baseline: StaticBaseline | None = None
    # Peer: runtime.rule_toolchain.verify, public.toolchains.capture.
    # AGENT: this is semflow.rule-toolchain/1, including full library digests;
    # never substitute an arbitrary pack path or just the platform pack name.
    query_pack: ArtifactRef


class HoldoutHandle(Contract):
    dataset_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    digest: Digest
    evaluator_profile: str = Field(min_length=1)


class RuleAcceptancePlan(Contract):
    fixture_validation: bool
    holdout: HoldoutHandle | None = None


class RuleGenerateInput(Contract):
    purpose: RulePurpose
    requirement: str = Field(min_length=10, max_length=5000)
    target: TargetBundle | None = None
    source_paths: tuple[RelativePath, ...] = ()
    strategy: Literal["auto", "model", "extend", "new_query"]
    corpus: CorpusSnapshot
    retrieval: RetrievalPolicy
    generation: RuleMethodPolicy
    development: DevelopmentPlan
    acceptance: RuleAcceptancePlan

    @model_validator(mode="after")
    def frozen_retrieval_space(self):
        if self.retrieval.mode != "bm25" and self.corpus.embedding is None:
            raise ValueError(
                "Vector retrieval requires a frozen embedding/index identity"
            )
        collections = [collection.name for collection in self.corpus.collections]
        if len(collections) != len(set(collections)):
            raise ValueError("Duplicate corpus collections")
        if set(collections) != {"reference", "rule_example"}:
            raise ValueError("Rule generation requires both frozen corpus collections")
        if self.retrieval.corpus_document_ids is not None:
            available = {
                identifier
                for c in self.corpus.collections
                for identifier in c.document_ids
            }
            if not set(self.retrieval.corpus_document_ids).issubset(available):
                raise ValueError("Requested document is outside the frozen corpus")
        return self


class RuleValidateInput(Contract):
    # WIRE-SEND:research.run — peer: public.rule_validation.assemble.
    # WIRE-RECV:research.run — peer: runtime.rule_validation.receive.
    # AGENT: validate rechecks the exact approved subjects from this immutable
    # generation manifest. It neither consumes/resumes that execution nor grants
    # platform publication. Replay evidence and holdout selection cannot change.
    # Optional for parsing historical structural requests; runtime rejects
    # absence before any validation tool runs.
    generation_manifest: ArtifactRef | None = None
    rule: EntityRef
    query: RuleRef
    fixtures: ArtifactRef
    approval: ApprovalDecision
    holdout: HoldoutHandle | None = None
    project_replay: ArtifactRef | None = None

    @model_validator(mode="after")
    def approved(self):
        if not self.approval.approved:
            raise ValueError("Validation requires approved fixtures")
        if self.rule.entity_id != self.query.rule_id:
            raise ValueError("Validation entity and query rule identity differ")
        return self


class RuleResult(Contract):
    # WIRE-SEND:research.rule_diagnostics — peer: runtime.rule_outputs.export / platform projection.
    # WIRE-RECV:research.rule_diagnostics — peer: public.rule_results.contents.
    # AGENT: diagnostics and independent_validation are evidence/status fields;
    # neither implies platform approval or publication.
    # Peer: rule_outputs.export / platform rule_projection. AGENT: historical
    # /1 checks_passed covered approved generated fixtures only. New /2 also
    # requires independent evaluation; old receipts must not be reinterpreted.
    validation_semantics: Literal[
        "semflow.rule-validation/1", "semflow.rule-validation/2"
    ] = "semflow.rule-validation/1"
    rule_id: UUID
    rule: RuleRef
    purpose: RulePurpose
    strategy: Literal["model", "extend", "new_query"]
    coverage_analysis: ArtifactRef
    fixtures: ArtifactRef
    retrieval_trace: ArtifactRef
    development_checks: tuple[ValidationReceipt, ...] = ()
    project_replay: ValidationReceipt | None = None
    technical_validation: ValidationReceipt | None = None
    # Peer: RuleService.validate -> rule_outputs.export -> platform projection.
    # AGENT: approved generated fixtures are development evidence. No selected
    # independent holdout means not_evaluated/draft, never publication eligibility.
    independent_validation: ValidationReceipt | None = None
    # Peer: rule_outputs.export -> public.rule_results.read_projection.
    # AGENT: method diagnostics preserve raw provenance/logs. Scientific statuses
    # remain the typed checks above; never derive publication from this JSON.
    diagnostics: ArtifactRef | None = None
    outcome: Literal["draft", "checks_passed", "needs_revision"]

    @model_validator(mode="after")
    def purpose_and_validation(self):
        if self.rule.rule_id != self.rule_id or self.rule.purpose != self.purpose:
            raise ValueError("Rule result identity or purpose does not match")
        if self.outcome == "checks_passed" and (
            self.technical_validation is None
            or self.technical_validation.status != "passed"
        ):
            raise ValueError("A draft is not a technically validated rule")
        if (
            self.outcome == "checks_passed"
            and self.validation_semantics == "semflow.rule-validation/2"
            and (
                self.independent_validation is None
                or self.independent_validation.status != "passed"
            )
        ):
            raise ValueError("Missing independent evaluation remains a draft")
        return self


class RuleDiagnostics(Contract):
    model_config = ConfigDict(json_schema_extra=schema_meaning("rule_diagnostics"))
    # WIRE-SEND:research.rule_diagnostics — peer: runtime.rule_diagnostics.read.
    schema_version: Literal["semflow.rule-diagnostics/1"] = "semflow.rule-diagnostics/1"
    execution_id: UUID
    title: str | None = None
    validation: dict
    files: dict[RelativePath, ArtifactRef]
