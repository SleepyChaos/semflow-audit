"""Freeze non-secret execution policy and prompt bytes before model execution."""

import hashlib
from pathlib import Path

from app.adapters.ai.policy import policy_snapshot
from app.contracts.stage_execution import default_version
from app.domain.audit import AuditError


def frozen_policy(spec):
    version = spec.prompt_version or default_version(spec.kind)
    policy = policy_snapshot(spec.kind)
    policy.update(spec.budget.model_dump(exclude_none=True))
    policy["execution_mode"] = "bounded"
    if spec.rule_experiment is not None:
        policy["rule_experiment"] = spec.rule_experiment.model_dump(
            mode="json", exclude_none=True
        )
    if spec.kind != "verification":
        path = (
            Path(__file__).resolve().parents[2]
            / "prompts"
            / f"{spec.kind}.v{version}.txt"
        )
        if not path.is_file():
            raise AuditError(f"Prompt version does not exist: {spec.kind}.v{version}")
        content = path.read_text(encoding="utf-8")
        policy["prompt_snapshot"] = {
            "purpose": spec.kind,
            "version": version,
            "content": content,
            "sha256": hashlib.sha256(content.encode()).hexdigest(),
        }
    return policy
