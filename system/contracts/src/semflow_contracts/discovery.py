"""Typed discovery operations, candidate assessments and coverage."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from semflow_contracts.baselines import StaticBaseline
from semflow_contracts.common import (
    ArtifactRef,
    BundleRef,
    Contract,
    Digest,
    EntityRef,
    RelativePath,
    SourceLocation,
)
from semflow_contracts.rule_values import RuleRef


class QueryPack(Contract):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    digest: Digest


class QuerySuite(Contract):
    name: str = Field(min_length=1)
    digest: Digest


class ScanInput(Contract):
    query_pack: QueryPack
    suite: QuerySuite
    supplemental_rules: tuple[RuleRef, ...] = ()
    build_profile: str = Field(min_length=1)


class WindowPolicy(Contract):
    version: str = Field(min_length=1)
    max_windows: int = Field(
        ge=0,
        description="0 schedules every eligible window, preserving the native scout method",
    )
    max_steps_per_window: int = Field(ge=1)
    max_calls: int | None = Field(ge=1)


class ScoutInput(Contract):
    # Peers: runtime.factory.internal_inputs / platform research_bridge.requests.
    # AGENT: preserve the native scheduling/read/window switches on both sides;
    # mapping only max_windows silently changes the scientific method.
    scope_paths: tuple[RelativePath, ...] = ()
    inspection_paths: tuple[RelativePath, ...] = ()
    scheduling_profile: Literal["full", "runtime_first"] = "full"
    include_third_party: bool = False
    window_lines: int = Field(default=100, ge=20, le=150)
    window_policy: WindowPolicy
    continuation: ArtifactRef | None = None


class ReviewPolicy(Contract):
    # Policy 1 preserves legacy navigation. Policy 2 enables repository gaps.
    # '-no-cache' is a continuation-only ablation for either policy.
    version: str = Field(min_length=1)
    batch_size: int = Field(ge=1)
    max_batches: int = Field(ge=0)
    supplement_insufficient: bool
    max_steps: int = Field(ge=1)
    max_context_chars: int = Field(ge=1)
    scope_paths: tuple[RelativePath, ...] = ()


class ReviewInput(Contract):
    baseline: StaticBaseline | None = None
    targets: BundleRef
    evidence: BundleRef
    source_execution_ids: tuple[UUID, ...] = Field(
        min_length=1,
        description="Exact leaf bundle producers, including empty successful bundles. An index coordinator does not replace the member producer identities.",
    )
    policy: ReviewPolicy

    @model_validator(mode="after")
    def unique_producers(self):
        if len(set(self.source_execution_ids)) != len(self.source_execution_ids):
            raise ValueError("Review source execution IDs cannot repeat")
        return self


class DiscoverInput(Contract):
    # Interface peer: runtime.dual_discovery.child_spec. These select algorithm
    # methods, independently of window/review policy and frozen Prompt versions.
    # AGENT: update the child producer and receiving kernel capability checks together.
    scout_method_version: str = Field(default="8", min_length=1)
    review_method_version: str = Field(default="12", min_length=1)
    scan: ScanInput | None = None
    scout: ScoutInput | None = None
    review: ReviewPolicy | None = None
    required_branches: tuple[Literal["scan", "scout"], ...] = Field(min_length=1)

    @model_validator(mode="after")
    def enabled_branches(self):
        enabled = {name for name in ("scan", "scout") if getattr(self, name)}
        if not enabled or not set(self.required_branches).issubset(enabled):
            raise ValueError("Required discovery branches must be enabled")
        if len(set(self.required_branches)) != len(self.required_branches):
            raise ValueError("Duplicate required branch")
        return self


class CandidateRecord(Contract):
    candidate_id: UUID
    execution_id: UUID
    origin: Literal["codeql", "scout", "review"]
    title: str = Field(min_length=1)
    description: str = Field(min_length=10)
    weakness: str = Field(pattern=r"^(unknown|CWE-[0-9]+)$")
    primary_location: SourceLocation
    identity_key: str = Field(min_length=1)
    static_finding_ref: EntityRef | None = None
    # Interface peers: bundle_io.import_targets / review_pool -> discovery_merge.
    # AGENT: review creates a new assessment candidate; this preserves the exact
    # source candidate identity. Missing review lineage must remain uncovered.
    derived_from: EntityRef | None = None
    related_target: EntityRef | None = None
    novelty: Literal["unknown", "known_location", "new_location", "new_root_cause"]
    evidence_refs: tuple[EntityRef, ...] = Field(min_length=1)
    # Interface peer: runtime.bundle_io imports this exact hypothesis context.
    # AGENT: unknown premises must survive discovery -> review; never replace with a verdict.
    context: ArtifactRef | None = Field(
        default=None,
        description="Versioned, hash-verified source hypothesis including unresolved premises; not a human decision.",
    )


class AssessmentRecord(Contract):
    assessment_id: UUID
    candidate_ref: EntityRef
    conclusion: Literal["supported", "excluded", "pending", "insufficient"]
    checked_premises: tuple[str, ...]
    unknown_premises: tuple[str, ...]
    evidence_refs: tuple[EntityRef, ...]
    counter_evidence_refs: tuple[EntityRef, ...] = ()
    reason: str = Field(min_length=10)

    @model_validator(mode="after")
    def conclusion_has_evidence(self):
        if self.conclusion in {"supported", "excluded"} and not self.evidence_refs:
            raise ValueError("A definite assessment requires evidence")
        if self.conclusion == "excluded" and not self.counter_evidence_refs:
            raise ValueError("Exclusion requires counter-evidence")
        return self


class CoverageReport(Contract):
    status: Literal["full", "partial", "none"]
    scope_manifest: ArtifactRef
    inspected_units: ArtifactRef
    missing_units: ArtifactRef
    reasons: tuple[str, ...] = ()
    reviewed_candidate_refs: tuple[EntityRef, ...] = ()
    unreviewed_candidate_refs: tuple[EntityRef, ...] = ()

    @model_validator(mode="after")
    def unreviewed_is_partial(self):
        if self.status == "full" and self.unreviewed_candidate_refs:
            raise ValueError("Unreviewed candidates cannot be full coverage")
        return self
