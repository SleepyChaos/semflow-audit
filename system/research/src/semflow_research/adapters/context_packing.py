"""Algorithm extracted from app.adapters.context_packing.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Reduce navigation overhead without deleting or truncating evidentiary bodies."""
import json
from copy import deepcopy


def context_size(context):
    return len(json.dumps(context, ensure_ascii=False))


def fit_navigation(context, maximum):
    if context_size(context) <= maximum:
        return context
    packed = deepcopy(context)
    removed = []
    for key in ("project_map", "source_inventory"):
        if key in packed:
            packed[key] = {
                "omitted_for_context": True,
                "meaning": "Navigation omitted; source tools and actual evidence remain available",
            }
            removed.append(key)
            if context_size(packed) <= maximum - 300:
                break
    packed["context_packing"] = {
        "omitted_navigation": removed,
        "evidence_preserved": True,
        "original_chars": context_size(context),
    }
    return packed
