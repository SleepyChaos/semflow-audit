"""Durable, version-checked source material and bounded model call receipts."""

import hashlib
import json
from pathlib import Path
from uuid import UUID

from app.adapters.snapshot import snapshot_digest
from app.core.audit_config import audit_settings
from app.domain.audit import AuditError
from app.services.evidence import EvidenceService, valid_evidence


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temporary.replace(path)


def frozen_call(
    provider,
    purpose,
    payload,
    schema,
    directory: Path,
    limit=None,
    ledger_directory=None,
):
    ledger_root = ledger_directory or directory.parent
    policy = semantic_policy(ledger_root)
    if limit is None:
        # Each understanding namespace and patch attempt is bounded by the
        # frozen graph policy. Reserve its actual maximum planned calls rather
        # than aborting a progressing repair at the old blanket 12-call cap.
        limit = policy.get("repair_call_limit", 12) if purpose == "repair" else 12
    serialized = json.dumps(payload, ensure_ascii=False)
    from app.adapters.repair.context_budget import context_limits

    limits = context_limits(purpose, payload, policy, len(serialized))
    save_json(
        directory / "payload-metrics.json",
        {
            "phase": payload.get("phase"),
            "characters": len(serialized),
            **limits,
            "fields": {
                key: len(json.dumps(value, ensure_ascii=False))
                for key, value in payload.items()
            },
        },
    )
    if limits["status"] == "rejected_context":
        raise AuditError(
            "关键上下文超过预算，需缩小目标；未截断原文", code="context_budget"
        )
    identity = digest({"payload": payload, "schema": schema.model_json_schema()})
    receipt = directory / "receipt.json"
    if receipt.exists():
        saved = json.loads(receipt.read_text())
        if saved["input_hash"] != identity or saved["output_hash"] != digest(
            saved["output"]
        ):
            raise AuditError("恢复时上下文或模型产物身份变化")
        return schema.model_validate(saved["output"])
    if (directory / "input.json").exists():
        raise AuditError("上次模型调用未完整提交，保留产物并创建新阶段")
    # Bound semantic calls as well as the existing stage provider budget.
    ledger = ledger_root / "calls.json"
    calls = json.loads(ledger.read_text()) if ledger.exists() else []
    if limit > 0 and len(calls) >= limit:
        raise AuditError("语义模型调用预算耗尽", code="budget_exhausted")
    save_json(directory / "input.json", {"input_hash": identity, "payload": payload})
    save_json(ledger, [*calls, {"input_hash": identity, "purpose": purpose}])
    response = provider.generate(purpose, payload, schema)
    output = response.model_dump(mode="json")
    save_json(
        receipt,
        {"input_hash": identity, "output_hash": digest(output), "output": output},
    )
    return response


def candidate_materials(evidence: EvidenceService, candidates) -> list[dict]:
    result = []
    for candidate in candidates:
        rows = valid_evidence(
            candidate.audit_id, [UUID(v) for v in candidate.evidence_ids]
        )
        for row in rows:
            if (
                row.snapshot_hash != evidence.audit.snapshot_hash
                or hashlib.sha256(row.content.encode()).hexdigest() != row.digest
            ):
                raise AuditError("源码证据版本或摘要不匹配")
            if row.kind == "code":
                fresh = evidence.read(**row.reference)
                if fresh["content"] != row.content:
                    raise AuditError("源码证据与实际文件窗口不一致")
                result.append(fresh)
            else:
                result.append(
                    {
                        "id": str(row.id),
                        "kind": row.kind,
                        "reference": row.reference,
                        "content": row.content,
                        "digest": row.digest,
                    }
                )
    return deduplicate(result)


def deduplicate(materials: list[dict]) -> list[dict]:
    return list(
        {
            digest({"reference": row["reference"], "digest": row["digest"]}): row
            for row in materials
        }.values()
    )


def project_inventory(evidence: EvidenceService, *, read_documents=True) -> dict:
    paths = sorted(
        p.relative_to(evidence.root).as_posix()
        for p in evidence.root.rglob("*")
        if p.is_file()
    )
    if len(paths) > 2000:
        raise AuditError("项目文件清单超过范围预算")
    docs = []
    for name in ("README.md", "pyproject.toml", "package.json", "requirements.txt"):
        path = evidence.root / name
        if path.is_file():
            docs.append(
                read_document(evidence, name)
                if read_documents
                else {"file": name, "status": "unread", "tool": "read_document"}
            )
    return {
        "files": paths,
        "documents": docs,
        "snapshot_hash": evidence.audit.snapshot_hash,
        "meaning": "Inventory and selected documents, not a complete project understanding",
    }


def read_document(evidence: EvidenceService, file: str, start_line=1, end_line=80):
    path = evidence.allowed(file)
    if path.suffix.lower() not in {
        ".md",
        ".txt",
        ".toml",
        ".json",
        ".yaml",
        ".yml",
        ".py",
        ".js",
        ".ts",
    }:
        raise AuditError("不支持读取此类项目文档")
    if path.name.startswith(".env") or any(
        p in {".git", ".venv", "node_modules"} for p in Path(file).parts
    ):
        raise AuditError("不能读取凭据或依赖工作目录")
    row = evidence.read(file, start_line, end_line)
    return row


def verify_snapshot(evidence):
    if snapshot_digest(evidence.root) != evidence.audit.snapshot_hash:
        raise AuditError("语义取证快照已变化")


def semantic_policy(directory: Path):
    """Resume uses DB-frozen limits; artifact edits cannot expand a stage budget."""
    defaults = {
        "context_chars": audit_settings.SEMANTIC_CONTEXT_CHARS,
        "repair_context_max_chars": audit_settings.SEMANTIC_REPAIR_MAX_CONTEXT_CHARS,
        "tool_limit": audit_settings.SEMANTIC_TOOL_LIMIT,
        "repair_attempts": audit_settings.REPAIR_ATTEMPTS,
        "repair_call_limit": (audit_settings.SEMANTIC_TOOL_LIMIT + 4)
        * audit_settings.REPAIR_ATTEMPTS,
    }
    path = directory / "semantic-policy.json"
    policy = json.loads(path.read_text()) if path.exists() else defaults
    try:
        stage_id = UUID(directory.name)
    except ValueError:
        stage_id = None  # Standalone local test/CLI artifacts have no stage identity.
    if stage_id:
        from app.persistence.stage_repository import StageRepository

        repository = StageRepository()
        stage = repository.get(str(stage_id))
        frozen = stage.model_config_snapshot.get("semantic_policy")
        if frozen is not None and path.exists() and frozen != policy:
            raise AuditError("语义预算配置产物被修改")
        policy = frozen or policy
        if frozen is None:
            repository.update(
                str(stage_id),
                model_config_snapshot={
                    **stage.model_config_snapshot,
                    "semantic_policy": policy,
                },
            )
    if not path.exists():
        save_json(path, policy)
    return policy
