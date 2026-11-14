"""Algorithm extracted from app.adapters.ai.provider_failures.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Safe transport diagnostics: never persist echoed bodies, URLs or credentials."""
import math
import re
from urllib.parse import urlparse


def failure_details(error, base_url):
    response = getattr(error, "response", None)
    status = getattr(error, "status_code", None)
    status = status if type(status) is int else None
    headers = response.headers if response is not None else {}
    request_id = getattr(error, "request_id", None) or headers.get("x-request-id")
    if (
        not isinstance(request_id, str)
        or not re.fullmatch("[A-Za-z0-9_-]{1,128}", request_id)
        or request_id.startswith(("sk-", "Bearer"))
    ):
        request_id = None
    retry_after = None
    try:
        seconds = float(headers.get("retry-after", ""))
        if math.isfinite(seconds) and 0 <= seconds <= 86400:
            retry_after = seconds
    except (TypeError, ValueError):
        pass
    kind = type(error).__name__
    cause = type(error.__cause__).__name__ if error.__cause__ else None
    family = (
        "rate_limit"
        if status == 429
        else "authentication"
        if status in {401, 403}
        else "server"
        if status is not None and status >= 500
        else "request"
        if status is not None and status >= 400
        else "timeout"
        if kind == "APITimeoutError"
        else "connection"
    )
    return {
        "exception_type": kind,
        "http_status": status,
        "provider_request_id": request_id,
        "endpoint_host": urlparse(str(base_url)).hostname,
        "failure_family": family,
        "transport_cause": cause,
        "retry_after_seconds": retry_after,
        "retryable_transport": family
        in {"rate_limit", "server", "timeout", "connection"},
    }
