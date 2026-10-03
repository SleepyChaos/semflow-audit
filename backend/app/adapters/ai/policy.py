"""Frozen non-secret model policy; all recovery shares one stage budget."""

from time import monotonic

from app.core.audit_config import audit_settings
from app.domain.audit import AuditError


def policy_snapshot() -> dict:
    return {
        "model": audit_settings.AI_MODEL,
        "base_url": audit_settings.AI_BASE_URL,
        "timeout": audit_settings.AI_TIMEOUT,
        "thinking_mode": audit_settings.AI_THINKING_MODE,
        "budgets": {
            purpose: getattr(audit_settings, f"AI_{purpose.upper()}_TOKENS")
            or audit_settings.AI_MAX_OUTPUT_TOKENS
            for purpose in ("review", "repair", "rule")
        },
        "max_calls": audit_settings.AI_STAGE_MAX_CALLS,
        "max_tokens": audit_settings.AI_STAGE_MAX_TOKENS,
        "max_seconds": audit_settings.AI_STAGE_MAX_SECONDS,
        "recovery_attempts": 1,
    }


class CallBudget:
    def __init__(self, policy: dict, records: list):
        self.policy, self.records = policy, records
        self.start = monotonic()

    def reserve(self, output: int, input_bound: int = 0) -> float:
        elapsed = sum(row.get("seconds", 0) for row in self.records)
        elapsed = max(elapsed, monotonic() - self.start)
        used = sum(
            (row["input_tokens"] + row["output_tokens"])
            if row.get("input_tokens") is not None
            and row.get("output_tokens") is not None
            else row.get("reserved_tokens", self.policy["max_tokens"])
            for row in self.records
        )
        if (
            len(self.records) >= self.policy["max_calls"]
            or used + output + input_bound > self.policy["max_tokens"]
            or elapsed >= self.policy["max_seconds"]
        ):
            raise AuditError(
                "model_budget_exhausted：阶段模型调用预算耗尽，结论未知",
                code="budget_exhausted",
            )
        return min(self.policy["timeout"], self.policy["max_seconds"] - elapsed)
