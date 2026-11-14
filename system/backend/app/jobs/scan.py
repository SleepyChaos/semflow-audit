from app.jobs.celery_app import celery_app
from app.runtime.scans import run_scan


@celery_app.task(name="audit.scan", time_limit=0, soft_time_limit=0)
def execute_scan(run_id: str) -> None:
    run_scan(run_id)
