"""Stable research entry points; no platform compatibility facades are imported."""

from semflow_contracts.wire import MEANINGS


def capabilities() -> dict:
    # Implemented means the CLI/Web decoupling boundary has been accepted.
    # It does not claim model efficacy or configured external tool availability.
    return {
        "delivery_status": "completed",
        "acceptance_scope": "core_cli_web_boundaries",
        "semantics_revisions": {
            value.contract_id: value.semantics_revision for value in MEANINGS.values()
        },
        "contract_versions": [
            "semflow.research.run/1.0",
            "semflow.research.result/1.0",
        ],
        "modules": {
            "discovery": {
                "declared": ["scan", "scout", "review", "discover"],
                "implemented": ["scan", "scout", "review", "discover"],
                "experimental": [],
            },
            "repair": {
                "declared": ["generate", "build_suite", "verify"],
                "implemented": ["generate", "build_suite", "verify"],
                "experimental": [],
                "implemented_engines": ["native", "openhands"],
                "experimental_engines": [],
            },
            "rules": {
                "declared": ["generate", "validate"],
                "implemented": ["generate", "validate"],
                "experimental": [],
                "implemented_methods": ["8"],
                "experimental_methods": [],
            },
        },
        "meaning": "CLI/Web decoupling acceptance is complete for discovery, native/OpenHands repair and method 8 RAG rules. Both callers use the same public kernels and contracts. Experimental lists contain only unaccepted entry points, disjoint from implemented. Model efficacy and live platform deployment are outside this acceptance; executions still require explicit compatible resources.",
    }
