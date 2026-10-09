import logging

from langgraph.checkpoint.postgres import PostgresSaver

from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.scanner import CodeQLScanner
from app.core.config import settings
from app.domain.audit import AuditCancelled
from app.jobs.celery_app import celery_app
from app.persistence.audit_repository import AuditRepository
from app.services.scanning import ScanService
from app.workflows.scanning import build_scan_graph

logger = logging.getLogger(__name__)


@celery_app.task(name="audit.scan")
def execute_scan(run_id: str) -> None:
    repository = AuditRepository()
    if not repository.claim(run_id):
        return
    try:
        service = ScanService(repository, ArtifactStore(), CodeQLScanner())
        url = str(settings.DATABASE_URL).replace(
            "postgresql+psycopg://", "postgresql://", 1
        )
        with PostgresSaver.from_conn_string(url) as saver:
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
