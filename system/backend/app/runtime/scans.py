"""Synchronous scan execution; task delivery stays outside the runtime."""

import logging

from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.scanner import CodeQLScanner
from app.domain.audit import AuditCancelled
from app.persistence.audit_repository import AuditRepository
from app.runtime.checkpoints import stage_checkpoints
from app.services.scanning import ScanService
from app.workflows.scanning import build_scan_graph

logger = logging.getLogger(__name__)


def run_scan(run_id: str):
    repository = AuditRepository()
    if not repository.claim(run_id):
        return repository.get(run_id)
    try:
        service = ScanService(repository, ArtifactStore(), CodeQLScanner())
        with stage_checkpoints() as saver:
            if repository.get(run_id).coverage.get("pipeline_version") == "2":
                from app.services.dual_scanning import DualScanService
                from app.workflows.dual_scanning import build_dual_scan_graph

                graph = build_dual_scan_graph(DualScanService(service), saver)
            else:
                graph = build_scan_graph(service, saver)
            graph.invoke(
                {"run_id": run_id}, config={"configurable": {"thread_id": run_id}}
            )
    except AuditCancelled:
        logger.info("Scan cancelled at stage boundary: %s", run_id)
    except Exception as exc:
        logger.exception("Scan stage failed: %s", run_id)
        try:
            repository.update(run_id, status="failed", error=str(exc)[:1000])
        except AuditCancelled:
            pass
    return repository.get(run_id)
