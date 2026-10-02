from celery import Celery

from app.core.audit_config import audit_settings

celery_app = Celery("audit", broker=audit_settings.REDIS_URL, include=["app.jobs.scan"])
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_time_limit=audit_settings.SCAN_TIMEOUT * 2 + 120,
)
