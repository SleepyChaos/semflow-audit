"""Reject candidate/semantic-contract conflicts before treating syntax as sufficient."""

from typing import Literal

from pydantic import Field

from app.contracts.stages import StrictModel
from app.domain.audit import AuditError
from app.services.context_materials import frozen_call


class ConstraintAssessment(StrictModel):
    fact_index: int = Field(ge=0)
    status: Literal["consistent", "conflicting", "unknown"]
    explanation: str = Field(min_length=10, max_length=1000)
    evidence_ids: list[str] = Field(min_length=1, max_length=10)


class CallerAssessment(StrictModel):
    obligation_id: int = Field(ge=0)
    status: Literal["preserved", "requested_change", "conflicting", "unknown"]
    explanation: str = Field(min_length=10, max_length=1000)
    evidence_ids: list[str] = Field(min_length=1, max_length=10)


class PatchAssessment(StrictModel):
    constraints: list[ConstraintAssessment] = Field(min_length=1, max_length=20)
    behavior_conflicts: list[str] = Field(default_factory=list, max_length=10)
    interpretation_conflicts: list[str] = Field(default_factory=list, max_length=10)
    callers: list[CallerAssessment] = Field(default_factory=list, max_length=8)
    limitation: str = Field(min_length=10, max_length=1000)


def check_contract(repair, state):
    bundle = repair.context(state)
    inspection = bundle["inspection"]
    facts = inspection["view"]["facts"]
    required = {i for i, fact in enumerate(facts) if fact.get("critical")}
    if not required:
        required = set(range(len(facts)))
    from app.adapters.repair.impact import caller_obligations

    impact = (
        caller_obligations(
            repair.service.evidence,
            state["proposal"]["changes"],
            repair.directory / f"attempt-{state['attempt']}/workspace",
        )
        if hasattr(repair.service, "evidence")
        else {"obligations": [], "evidence": []}
    )
    evidence = [*inspection["evidence"], *impact.pop("evidence")]
    # context() aliases complete file bodies to allowed_files. Both are supplied
    # here; original evidence IDs and immutable receipts retain their meaning.
    response = frozen_call(
        repair.service.provider,
        "repair",
        {
            "phase": "assess_patch_contract",
            "targets": bundle["targets"],
            "semantic_contract": inspection["view"],
            "required_fact_indices": sorted(required),
            "acceptance_contract": bundle.get("acceptance_contract"),
            "proposal": state["proposal"],
            "caller_impact": impact,
            "allowed_files": bundle["allowed_files"],
            "evidence": evidence,
            "meaning": "Independent consistency check only, not executed security proof. Compare original and proposed behavior against every critical fact and modification semantics. Existing behavior outside the requested repair must remain. Unknown compatibility is not consistent.",
        },
        PatchAssessment,
        repair.directory / f"contract-call-{state['attempt']}",
    )
    known = {row["id"] for row in evidence}
    indices = [row.fact_index for row in response.constraints]
    if (
        len(indices) != len(set(indices))
        or not required.issubset(indices)
        or any(
            row.fact_index >= len(facts) or not set(row.evidence_ids).issubset(known)
            for row in response.constraints
        )
    ):
        raise AuditError(
            "补丁约束检查未覆盖必需事实或引用无效", code="evidence_insufficient"
        )
    expected = {row["id"] for row in impact["obligations"]}
    assessed = [row.obligation_id for row in response.callers]
    caller_sources = {row["id"]: row["evidence_id"] for row in impact["obligations"]}
    if (
        set(assessed) != expected
        or len(assessed) != len(set(assessed))
        or any(
            not set(row.evidence_ids).issubset(known)
            or caller_sources.get(row.obligation_id) not in row.evidence_ids
            for row in response.callers
        )
    ):
        raise AuditError(
            "共享函数调用影响检查不完整或引用无效", code="evidence_insufficient"
        )
    failures = [
        row.explanation for row in response.constraints if row.status != "consistent"
    ]
    failures.extend(
        row.explanation
        for row in response.callers
        if row.status in {"conflicting", "unknown"}
    )
    failures.extend(response.behavior_conflicts)
    failures.extend(response.interpretation_conflicts)
    writable = set(bundle["allowed_files"])
    original_ranges = [
        row["reference"] for row in inspection["evidence"] if row["kind"] == "code"
    ]
    missing = any(
        row["kind"] == "code"
        and row["reference"]["file"] in writable
        and not any(
            ref.get("file") == row["reference"]["file"]
            and ref.get("start_line", 0) <= row["reference"]["start_line"]
            and ref.get("end_line", 0) >= row["reference"]["end_line"]
            for ref in original_ranges
        )
        for row in evidence
    )
    return {
        "status": "failed" if failures else "passed",
        "source_context_missing": missing,
        "output": "; ".join(failures)
        if failures
        else "No model-observed semantic contract conflict",
        "assessment": response.model_dump(mode="json"),
        "caller_impact": impact,
        "limitation": "Model consistency assessment only; execution and human acceptance remain separate requirements",
    }


def contract_diagnosis(checks):
    check = checks.get("semantic_contract")
    if (
        not check
        or check["status"] != "failed"
        or any(
            row["status"] not in {"passed", "not_run"}
            for name, row in checks.items()
            if name != "semantic_contract"
        )
    ):
        return None
    interpretation = check["assessment"].get("interpretation_conflicts", [])
    uncertain = any(
        row["status"] == "unknown" for row in check["assessment"].get("callers", [])
    ) or any(row["status"] == "unknown" for row in check["assessment"]["constraints"])
    return {
        "category": "understanding"
        if interpretation or check.get("source_context_missing")
        else "inconclusive"
        if uncertain
        else "implementation",
        "summary": check["output"],
        "violated_constraints": [
            row["explanation"]
            for row in check["assessment"]["constraints"]
            if row["status"] != "consistent"
        ]
        + [
            row["explanation"]
            for row in check["assessment"].get("callers", [])
            if row["status"] in {"conflicting", "unknown"}
        ]
        + check["assessment"].get("behavior_conflicts", [])
        + interpretation,
        "next_action": "Reinterpret the original request and source; do not treat the prior model view as authorization"
        if interpretation or check.get("source_context_missing")
        else "Resolve missing evidence before claiming compatibility"
        if uncertain
        else "Revise only the concrete candidate/contract conflicts while preserving successful changes",
        "origin": "persisted_semantic_contract_assessment; no second diagnostic model call",
    }


def impact_materials(service, checks):
    """Bring actual caller reads into a new understanding, never invented IDs."""
    from types import SimpleNamespace

    from app.services.context_materials import candidate_materials

    identifiers = [
        row["evidence_id"]
        for row in checks.get("semantic_contract", {})
        .get("caller_impact", {})
        .get("obligations", [])
    ]
    if not identifiers:
        return []
    return candidate_materials(
        service.evidence,
        [
            SimpleNamespace(
                audit_id=service.stage.audit_id,
                evidence_ids=list(dict.fromkeys(identifiers)),
            )
        ],
    )
