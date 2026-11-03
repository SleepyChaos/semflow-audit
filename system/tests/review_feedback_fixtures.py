"""Synthetic data-flow controls and explicit model doubles for feedback regression."""

from copy import deepcopy

from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import StageRun
from app.persistence.stage_repository import StageRepository
from app.services.review import ReviewService
from sqlmodel import Session

OPERATION = "value = eval(policy.accept(input()))"
FILES = {
    "app.py": "policy = __import__('controls')\n"
    + OPERATION
    + "\nother = eval(input())\n",
    "controls.py": "def accept(value):\n    return value\n",
}


def make_service(
    ctx, model, *, seed=False, siblings=False, copies=1, version="10", **inputs
):
    with Session(engine) as db:
        audit = db.get(AuditRun, ctx["run_id"])
        finding = deepcopy(audit.findings[0])
        finding["locations"][0]["line"] = 2
        finding["tags"] = ["CWE-94"]
        audit.findings = [
            {**deepcopy(finding), "id": f"target-{i}"} for i in range(copies)
        ]
        if siblings:
            second = deepcopy(finding)
            second["id"] = "second-operation"
            second["locations"][0]["line"] = 3
            audit.findings = [finding, second]
        db.add(audit)
        stage = StageRun(
            audit_id=ctx["run_id"],
            kind="review",
            prompt_version=version,
            inputs={"discover": False, **inputs},
        )
        db.add(stage)
        db.commit()
        db.refresh(stage)
        identifier = str(stage.id)
    StageRepository().claim(identifier)
    service = ReviewService(identifier, model)
    if seed:
        service.seeded_page = service.evidence.read("controls.py", 1, 151)
    return service


class FeedbackModel:
    model = "explicit-feedback-regression-double"

    def __init__(self, mode="supported", max_calls=8):
        self.mode, self.seen = mode, []
        self.policy = {"max_calls": max_calls}
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

    def generate(self, purpose, payload, schema):
        assert purpose == "review"
        self.usage["calls"] += 1
        self.seen.append(deepcopy(payload))
        followup = bool(payload.get("feedback_revision"))
        if followup and self.mode == "provider_failure":
            raise AuditError(
                "synthetic supplemental provider interruption", code="provider_error"
            )
        controls = next(
            (
                p
                for p in payload["evidence"]
                if p["reference"].get("file") == "controls.py"
            ),
            None,
        )
        assessments = []
        for target in payload["targets"]:
            source = next(
                p
                for p in payload["evidence"]
                if p["kind"] == "code"
                and p["reference"].get("file") == "app.py"
                and p["reference"]["start_line"]
                <= target["location"]["line"]
                <= p["reference"]["end_line"]
            )
            secondary = target["location"]["line"] == 3
            quote = "other = eval(input())" if secondary else OPERATION
            missing = not secondary and (not controls or self.mode == "still_missing")
            state = (
                "insufficient"
                if missing
                else "excluded"
                if self.mode == "excluded" and not secondary
                else "supported"
            )
            protection_quote = "return '1'" if state == "excluded" else "return value"
            ids = [source["id"]] + (
                [controls["id"]] if controls and not secondary else []
            )
            checks = []
            for role in ("operation", "input_or_policy", "unsafe_protection"):
                protection = role == "unsafe_protection" and not secondary
                status = (
                    "missing"
                    if protection and missing
                    else "contradicted"
                    if protection and state == "excluded"
                    else "established"
                )
                checks.append(
                    {
                        "premise": role,
                        "status": status,
                        "reason": "需要读取 controls.py 并核对真实保护路径。"
                        if status == "missing"
                        else "实际源码和返回值支持这一前提状态。",
                        "evidence_ids": [controls["id"]]
                        if protection and controls
                        else [source["id"]],
                        "quote": ""
                        if status == "missing"
                        else protection_quote
                        if protection
                        else quote,
                    }
                )
            assessments.append(
                {
                    "candidate_id": target["candidate_id"],
                    "assessment": state,
                    "weakness": "CWE-94",
                    "security_property": target["security_property"],
                    "reason": "依据真实输入、操作和关联控制源码进行逐前提复核。",
                    "checked_premises": ["读取实际输入和 eval 操作。"],
                    "missing_premises": ["controls.py 的实际保护实现尚未核实。"]
                    if missing
                    else [],
                    "evidence_ids": ids,
                    "counterevidence_ids": [controls["id"]]
                    if state == "excluded"
                    else [],
                    "premises": checks,
                }
            )
        if followup and self.mode == "invalid_revision":
            from uuid import uuid4

            assessments[0]["premises"][-1]["evidence_ids"] = [str(uuid4())]
        if followup and self.mode == "pending_revision":
            assessments[0]["assessment"] = "pending"
        return schema.model_validate(
            {"action": "final", "candidate_assessments": assessments}
        )
