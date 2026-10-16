"""Classify writable target support before evidence gathering or paid generation."""

from pathlib import Path

from app.adapters.repair.patches import safe_file
from app.domain.audit import AuditError


def target_readiness(root, paths):
    if not paths or len(paths) > 30:
        return {"status": "unsupported_target", "reason": "需要明确有限的可修改文件"}
    try:
        for name in paths:
            path = safe_file(root, name)
            if not path.is_file():
                raise AuditError("修复目标文件不存在")
    except AuditError as error:
        return {"status": "forbidden_target", "reason": str(error)}
    if not any(Path(p).suffix in {".py", ".js", ".jsx", ".ts", ".tsx"} for p in paths):
        return {"status": "unsupported_target", "reason": "模板或配置单独修复尚不支持"}
    return {"status": "eligible", "paths": paths}


def require_targets(root, paths):
    if paths:
        result = target_readiness(root, paths)
        if result["status"] != "eligible":
            raise AuditError(
                result["reason"],
                code="unsupported_repair_target"
                if result["status"] == "unsupported_target"
                else "forbidden_repair_target",
            )
