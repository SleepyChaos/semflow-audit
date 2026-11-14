"""Combine an external engine ledger with native calls without mutating budgets."""

import json


def combined_usage(native, directory):
    native = dict(native.get("native", native))
    receipt = directory / "openhands/runtime-result.json"
    if not receipt.parent.exists():
        return dict(native)
    try:
        runtime = json.loads(receipt.read_text())
    except OSError, ValueError:
        runtime = {"status": "unknown"}
    metrics = runtime.get("metrics", {})
    tokens = metrics.get("accumulated_token_usage") or {}
    unknown = (
        runtime.get("status") != "completed"
        and runtime.get("error_code") != "MaxIterationsReached"
    )
    external = {
        "calls": len(metrics["token_usages"]) if "token_usages" in metrics else None,
        "input_tokens": tokens.get("prompt_tokens"),
        "output_tokens": tokens.get("completion_tokens"),
        "unknown_requests_possible": unknown,
        "provider_cost_usd": None,
    }
    return {
        **native,
        **{
            key: (native.get(key) or 0) + (external.get(key) or 0)
            for key in ("calls", "input_tokens", "output_tokens")
        },
        "native": dict(native),
        "external_engines": {"openhands": external},
        "known_usage_only": unknown
        or any(external[k] is None for k in ("calls", "input_tokens", "output_tokens")),
    }
