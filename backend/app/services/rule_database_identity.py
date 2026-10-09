"""Original database coverage checks before a missing-target claim."""

import hashlib
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import yaml

from app.domain.audit import AuditError


def verify_database(database, root, audit, files):
    metadata = yaml.safe_load((database / "codeql-database.yml").read_text())
    if (
        Path(metadata.get("sourceLocationPrefix", "")).resolve() != root.resolve()
        or metadata.get("primaryLanguage") != audit.language
        or metadata.get("creationMetadata", {}).get("cliVersion")
        != audit.codeql_version
        or not metadata.get("finalised")
    ):
        raise AuditError("原项目数据库来源、版本或抽取状态不匹配")
    archive = database / "src.zip"
    if not archive.is_file():
        raise AuditError("缺少数据库源码归档，无法核对目标文件覆盖")
    coverage = {}
    try:
        with ZipFile(archive) as source:
            for name in files:
                path = (root / name).resolve()
                if not path.is_relative_to(root.resolve()) or not path.is_file():
                    raise AuditError("目标文件不在冻结项目中")
                member = path.as_posix().lstrip("/")
                original = path.read_bytes()
                if member not in source.namelist() or source.read(member) != original:
                    raise AuditError("目标源码未被原数据库完整归档，不能声称基线漏检")
                coverage[name] = hashlib.sha256(original).hexdigest()
    except (BadZipFile, KeyError) as exc:
        raise AuditError("原数据库源码归档无效") from exc
    # A successful process exit is insufficient when extraction recorded errors.
    for path in (database / "diagnostic").rglob("*.jsonl"):
        for line in path.read_text().splitlines():
            item = json.loads(line)
            location = item.get("location", {}).get("file")
            if item.get("severity") == "error" and (
                not location or any(str(root / name) == location for name in files)
            ):
                raise AuditError("原数据库目标抽取存在错误，漏检基线无效")
    return {
        "files": coverage,
        "scope": "Exact archived source and target extraction diagnostics; not complete semantic coverage",
    }
