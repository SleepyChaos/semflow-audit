"""Embedding spaces never mix across endpoint, revision or preprocessing."""

import hashlib
import json

from app.core.audit_config import audit_settings as settings


def embedding_identity() -> str:
    configuration = {
        "endpoint": settings.AI_BASE_URL.rstrip("/"),
        "model": settings.EMBEDDING_MODEL,
        "revision": settings.EMBEDDING_REVISION,
        "dimensions": settings.EMBEDDING_DIMENSIONS,
        "protocol": "openai-text-float",
        "preprocessing": "exact-chunk-text-v1",
    }
    return hashlib.sha256(
        json.dumps(configuration, sort_keys=True).encode()
    ).hexdigest()
