"""Security properties and source-cited proof obligations for discovery V6/V8."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from app.contracts.scouting import CompactTaskCheck, FocusedFinding, ScoutResponseV5
from app.contracts.stages import StrictModel
from app.contracts.unified_review import CheckedAssessment, UnifiedReviewResponse

SecurityProperty = Literal[
    "authentication",
    "authorization",
    "object_ownership",
    "input_injection",
    "output_encoding",
    "state_integrity",
    "secrets_config",
    "rate_limiting",
    "security_logging",
    "other",
]


class LocatedFinding(FocusedFinding):
    security_property: SecurityProperty
    route_id: str = Field(default="", max_length=40)
    operation_quote: str = Field(min_length=3, max_length=300)
    endpoint: str = Field(default="", max_length=120)


class RouteCheck(StrictModel):
    route_id: str
    authentication: Literal[
        "missing_authentication", "protected", "public_expected", "unknown"
    ]
    reason: str = Field(min_length=10, max_length=240)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=6)


class SemanticTaskCheck(CompactTaskCheck):
    conclusion: Literal[
        "suspicious", "no_condition_identified", "unknown", "not_applicable"
    ] = "unknown"


class ScoutResponseV6(ScoutResponseV5):
    route_checks: list[RouteCheck] = Field(default_factory=list, max_length=40)
    findings: list[LocatedFinding] = Field(default_factory=list, max_length=16)
    task_checks: list[SemanticTaskCheck] = Field(default_factory=list, max_length=10)


class FinalScoutResponseV6(ScoutResponseV6):
    action: Literal["final"] = "final"
    tool: None = None


class PremiseCheck(StrictModel):
    policy_basis: Literal[
        "explicit_contract", "source_security_requirement", "unknown", "not_applicable"
    ] = "unknown"
    premise: Literal["operation", "input_or_policy", "unsafe_protection"]
    status: Literal["established", "contradicted", "missing", "not_applicable"]
    reason: str = Field(min_length=10, max_length=300)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=6)
    quote: str = Field(default="", max_length=300)


class SemanticAssessment(CheckedAssessment):
    security_property: SecurityProperty
    premises: list[PremiseCheck] = Field(min_length=3, max_length=3)


class UnifiedReviewResponseV8(UnifiedReviewResponse):
    candidate_assessments: list[SemanticAssessment] = Field(
        default_factory=list, max_length=50
    )


class FinalUnifiedReviewResponseV8(UnifiedReviewResponseV8):
    action: Literal["final"] = "final"
    tool: None = None
