"""Route only this process's real API/Worker tasks to an isolated test queue."""

import os

from app.jobs.celery_app import celery_app

queue = os.environ["SEMFLOW_TEST_QUEUE"]
if not queue.startswith("semflow-chain-"):
    raise RuntimeError("A dedicated supplemental queue is required")
celery_app.conf.update(
    task_default_queue=queue,
    task_routes={
        name: {"queue": queue}
        for name in ("audit.scan", "audit.stage", "audit.knowledge_index")
    },
)

from app.main import app  # noqa: F401 - configure dispatch before route imports
