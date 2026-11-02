"""Persistent graph checkpoints, independent of the delivery mechanism."""

from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver

from app.core.config import settings


@contextmanager
def stage_checkpoints():
    url = str(settings.DATABASE_URL).replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    with PostgresSaver.from_conn_string(url) as saver:
        yield saver
