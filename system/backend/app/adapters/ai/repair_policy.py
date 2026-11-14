"""Independent repair limits; other stages and existing frozen policies stay intact."""

from app.core.audit_config import audit_settings
from app.domain.audit import AuditError


def repair_policy():
    total = audit_settings.REPAIR_SOURCE_TOOL_LIMIT
    initial = audit_settings.REPAIR_INITIAL_SOURCE_TOOL_LIMIT
    calls = audit_settings.REPAIR_MODEL_CALL_LIMIT
    if not 1 <= initial <= total or calls < 1:
        raise AuditError("修复取证/模型预算无效；不能以调整工具次数隐式扩大模型调用")
    return validate(
        {
            "context_chars": audit_settings.SEMANTIC_CONTEXT_CHARS,
            "repair_context_max_chars": audit_settings.SEMANTIC_REPAIR_MAX_CONTEXT_CHARS,
            "tool_limit": total,
            "source_tool_limit": total,
            "initial_source_tool_limit": initial,
            "repair_call_limit": calls,
            "repair_attempts": audit_settings.REPAIR_ATTEMPTS,
            "source_budget_version": 1,
        }
    )


def new_stage_policy(kind, version):
    """Only newly created modern repair stages opt in; resume never calls this."""
    if kind != "repair" or version not in {"3", "4"}:
        return {}
    from app.adapters.ai.policy import policy_snapshot

    return {**policy_snapshot("repair"), "semantic_policy": repair_policy()}


def validate(policy):
    if "source_budget_version" not in policy:
        return policy  # Historical policy stays byte-for-byte compatible.
    required = (
        "source_tool_limit",
        "initial_source_tool_limit",
        "repair_call_limit",
        "repair_attempts",
    )
    if policy["source_budget_version"] != 1 or any(
        type(policy.get(key)) is not int or policy[key] < 1 for key in required
    ):
        raise AuditError("修复预算冻结策略无效", code="integrity_error")
    if (
        policy.get("tool_limit") != policy["source_tool_limit"]
        or policy["initial_source_tool_limit"] > policy["source_tool_limit"]
    ):
        raise AuditError("修复源码预算字段不一致", code="integrity_error")
    return policy
