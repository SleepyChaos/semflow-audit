"""Frozen non-secret model policy; all recovery shares one stage budget."""

from time import monotonic

from app.core.audit_config import audit_settings
from app.domain.audit import AuditError


def policy_snapshot(kind: str | None = None) -> dict:
    policy = {
        "model": audit_settings.AI_MODEL,
        "base_url": audit_settings.AI_BASE_URL,
        "timeout": audit_settings.AI_TIMEOUT,
        "thinking_mode": audit_settings.AI_THINKING_MODE,
        "budgets": {
            purpose: getattr(audit_settings, f"AI_{purpose.upper()}_TOKENS")
            or audit_settings.AI_MAX_OUTPUT_TOKENS
            for purpose in ("review", "repair", "rule", "scout")
        }
        | {
            "report": audit_settings.AI_MAX_OUTPUT_TOKENS,
            "verification_suite": audit_settings.AI_MAX_OUTPUT_TOKENS,
        },
        "max_calls": audit_settings.AI_STAGE_MAX_CALLS,
        "max_tokens": audit_settings.AI_STAGE_MAX_TOKENS,
        "max_seconds": audit_settings.AI_STAGE_MAX_SECONDS,
        "recovery_attempts": 1,
        "connection_retry_delays": [2, 4, 8],
    }
    if kind == "rule":
        # CodeQL compilation and fixture execution have their own command limits.
        # They must not consume the model's recovery-call time budget.
        policy["seconds_scope"] = "model_calls"
    if kind in {"scout", "review", "repair"}:
        policy["execution_mode"] = audit_settings.AI_AUDIT_EXECUTION_MODE
        policy["max_no_progress"] = max(1, audit_settings.AI_STAGE_MAX_NO_PROGRESS)
        if policy["execution_mode"] == "progress":
            policy.update(max_calls=0, max_tokens=0, max_seconds=0)
    return policy


class CallBudget:
    def __init__(self, policy: dict, records: list):
        self.policy, self.records = policy, records
        self.start = monotonic()

    def reserve(self, output: int, input_bound: int = 0) -> float:
        elapsed = sum(row.get("seconds", 0) for row in self.records)
        if self.policy.get("seconds_scope") != "model_calls":
            elapsed = max(elapsed, monotonic() - self.start)
        used = sum(
            (row["input_tokens"] + row["output_tokens"])
            if row.get("input_tokens") is not None
            and row.get("output_tokens") is not None
            else row.get("reserved_tokens", self.policy["max_tokens"])
            for row in self.records
        )
        limits = {
            "calls": (len(self.records) + 1, self.policy["max_calls"]),
            "tokens": (used + output + input_bound, self.policy["max_tokens"]),
            "seconds": (elapsed, self.policy["max_seconds"]),
        }
        exceeded = [
            name
            for name, (requested, limit) in limits.items()
            if limit > 0
            and (requested >= limit if name == "seconds" else requested > limit)
        ]
        if exceeded:
            raise AuditError(
                "model_budget_exhausted：阶段预算不足（"
                + ", ".join(
                    f"{name}={limits[name][0]:.0f}/{limits[name][1]}"
                    for name in exceeded
                )
                + "），结论未知",
                code="budget_exhausted",
            )
        return (
            min(self.policy["timeout"], self.policy["max_seconds"] - elapsed)
            if self.policy["max_seconds"] > 0
            else self.policy["timeout"]
        )


def stalled(rows, policy):
    """Persisted receipts distinguish real investigation from repeated failure."""
    if policy.get("execution_mode") != "progress":
        return False
    limit = policy.get("max_no_progress", 3)
    return (
        len(rows) >= limit
        and all(
            row.get("status") == "incomplete"
            # A validated structured attempt on a different candidate is investigation,
            # even when its proof gate rejects the verdict. Local step limits bound
            # retries; this must not suppress unrelated subsequent candidates.
            or (
                row.get("status") == "partial"
                and not row.get("recommendations")
                and not row.get("rejected_assessments")
            )
            for row in rows[-limit:]
        )
    )
