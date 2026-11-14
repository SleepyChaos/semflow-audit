"""Algorithm extracted from app.adapters.retrieval.embedding_identity.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Embedding spaces never mix across endpoint, revision or preprocessing."""
import hashlib
import json


def embedding_identity(*, _kernel) -> str:
    configuration = {
        "endpoint": _kernel.settings.AI_BASE_URL.rstrip("/"),
        "model": _kernel.settings.EMBEDDING_MODEL,
        "revision": _kernel.settings.EMBEDDING_REVISION,
        "dimensions": _kernel.settings.EMBEDDING_DIMENSIONS,
        "protocol": "openai-text-float",
        "preprocessing": "exact-chunk-text-v1",
    }
    return hashlib.sha256(
        json.dumps(configuration, sort_keys=True).encode()
    ).hexdigest()
