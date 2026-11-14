"""Task-scoped source reads: durable execution counts, cache reuse and reservation."""

import json
from hashlib import sha256

from app.domain.audit import AuditError
from app.services.context_materials import digest, save_json, verify_snapshot
from app.services.inspection_progress import existing_read


def enabled(policy):
    return policy.get("source_budget_version") == 1


def _rows(directory):
    path = directory / "semantics/tools.json"
    rows = json.loads(path.read_text()) if path.exists() else []
    state = directory / "source-budget.json"
    if state.exists() and json.loads(state.read_text())["ledger_hash"] != digest(rows):
        raise AuditError("修复取证账本或计数产物变化", code="integrity_error")
    return rows


def summary(directory, policy):
    rows = _rows(directory)
    spent = [r for r in rows if not r.get("reused", False)]
    total = policy["source_tool_limit"]
    initial = sum(r.get("namespace") == "initial" for r in spent)
    return {
        "stage_id": directory.name,
        "snapshot_hash": rows[0]["snapshot"] if rows else None,
        "requested": len(rows),
        "executions_or_rejected": len(spent),
        "executed": sum(r.get("status") == "executed" for r in spent),
        "rejected": sum(r.get("status") == "rejected" for r in spent),
        "incomplete": sum(r.get("status") == "pending" for r in spent),
        "reused": len(rows) - len(spent),
        "remaining": max(0, total - len(spent)),
        "initial_used": initial,
        "initial_remaining": max(
            0, min(total - len(spent), policy["initial_source_tool_limit"] - initial)
        ),
        "ledger_hash": digest(rows),
    }


def remaining(directory, policy, namespace):
    counts = summary(directory, policy)
    return (
        counts["initial_remaining"] if namespace == "initial" else counts["remaining"]
    )


def _commit(directory, rows, policy):
    save_json(directory / "semantics/tools.json", rows)
    # The ledger is authoritative while committing its matching count receipt.
    (directory / "source-budget.json").unlink(missing_ok=True)
    save_json(directory / "source-budget.json", summary(directory, policy))


def read(reader, call, materials, *, namespace, step=None):
    verify_snapshot(reader.evidence)
    policy, directory = reader.policy, reader.directory
    rows = _rows(directory)
    snapshot = reader.evidence.audit.snapshot_hash
    key = digest(
        {"snapshot": snapshot, "name": call["name"], "arguments": call["arguments"]}
    )
    if call["name"] in {"read_source", "read_document"}:
        reader.evidence.allowed(call["arguments"].get("file", ""))
    if any(r.get("snapshot") != snapshot for r in rows):
        raise AuditError("取证账本不属于当前源码快照", code="identity_error")
    for row in rows:
        if "result" in row and row.get("result_hash") != digest(row["result"]):
            raise AuditError("取证缓存内容变化", code="integrity_error")
    previous = next(
        (
            r
            for r in rows
            if r.get("namespace") == namespace
            and r.get("step") == step
            and r.get("key") == key
            and step is not None
        ),
        None,
    )
    if previous:
        if "result" not in previous:
            raise AuditError("上次源码工具未完整提交，保留现场", code="integrity_error")
        return previous["result"], previous.get("reused", False)
    cached = next(
        (r["result"] for r in rows if r.get("key") == key and "result" in r), None
    )
    if cached is None:
        from app.services.rule_preparation_context import source_windows

        lengths = {
            r["file"]: r["total_lines"]
            for r in source_windows(reader.evidence, materials)
        }
        cached = existing_read(call, materials, [], file_lengths=lengths)
    if cached is not None:
        if (
            cached.get("content") is not None
            and cached.get("digest") != sha256(cached["content"].encode()).hexdigest()
        ):
            raise AuditError("取证正文摘要不一致", code="integrity_error")
        consecutive = 0
        for row in reversed(rows):
            if not row.get("reused"):
                break
            consecutive += 1
        if consecutive >= 2:
            raise AuditError(
                "连续重复取证未产生新证据，停止无进展请求", code="source_stalled"
            )
        data, reused = cached, True
    else:
        if remaining(directory, policy, namespace) <= 0:
            raise AuditError(
                "修复源码执行预算耗尽；保留后续阶段额度", code="budget_exhausted"
            )
        data, reused = None, False
    entry = {
        "namespace": namespace,
        "step": step,
        "key": key,
        "snapshot": snapshot,
        "call": call,
        "reused": reused,
        "status": "pending",
    }
    rows.append(entry)
    _commit(directory, rows, policy)
    if data is None:
        try:
            data = reader.read_tool(call)
        except AuditError as error:
            entry.update(status="rejected", reason=str(error))
            _commit(directory, rows, policy)
            raise
    entry.update(
        status="reused" if reused else "executed", result=data, result_hash=digest(data)
    )
    _commit(directory, rows, policy)
    return data, reused
