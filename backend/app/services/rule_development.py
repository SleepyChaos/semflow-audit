"""Durable development fixture executions, separate from independent evaluation."""

import json
import shutil
from uuid import uuid4

from app.adapters.codeql.custom import (
    fixed_dependencies,
    query_digest,
    validate_fixtures,
)
from app.adapters.snapshot import snapshot_digest
from app.domain.audit import AuditError
from app.services.context_materials import digest, save_json


def execute_development(
    service, pack, response, fixtures, attempt, runner=validate_fixtures
):
    identity = digest(
        {
            "query": query_digest(response.query, response.modules),
            "fixtures": fixtures,
            "dependencies": fixed_dependencies(service.audit.language),
        }
    )
    receipt, feedback = (
        pack / "development-receipt.json",
        pack / "development_feedback.json",
    )
    if receipt.exists():
        saved = json.loads(receipt.read_text())
        result = json.loads(feedback.read_text())
        if saved["identity"] != identity or saved["result_hash"] != digest(result):
            raise AuditError("开发样例执行产物被修改")
        directory = (service.directory / saved["directory"]).resolve()
        if not directory.is_relative_to(service.directory.resolve()):
            raise AuditError("开发样例执行目录无效")
        if any(
            snapshot_digest(directory / kind) != check["snapshot_hash"]
            for kind, check in result["tests"].items()
        ):
            raise AuditError("开发样例源码被修改")
        return result
    directory = service.directory / f"development-{attempt - 1}-{uuid4()}"
    try:
        result = runner(directory, pack, service.audit.language, fixtures)
    finally:
        log = directory / "execution.log"
        if log.is_file():
            shutil.copyfile(log, pack / "development-execution.log")
    save_json(feedback, result)
    save_json(
        receipt,
        {
            "identity": identity,
            "result_hash": digest(result),
            "directory": str(directory.relative_to(service.directory)),
        },
    )
    return result
