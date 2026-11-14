"""Algorithm extracted from app.adapters.codeql.type_probe.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Bounded read-only LSP hover probe, absent tool is explicit unavailability."""
import json
import os
import re
import signal
import subprocess
from pathlib import Path

from semflow_research.adapters.codeql.custom import search_paths
from semflow_research.adapters.codeql.process import ENV_KEYS

AUTHOR_COMMIT = "a33ea82bba156dc8352a0ecd85baff34cbb950ed"


def probe_types(pack, *, _kernel):
    client = _kernel.settings.CODEQL_LSP_CLIENT
    if client is None or not client.is_file():
        return {
            "status": "unavailable",
            "reason": "Pinned author LSP client not installed",
        }
    source = pack / "generated.ql"
    positions = []
    for line, text in enumerate(source.read_text().splitlines()):
        for match in re.finditer(
            "\\b(?:Node|Expr|Call|CfgNode|CallCfgNode|ExprNode|getArg|getArgument|asExpr|asCfgNode|flow|isSource|isSink)\\b",
            text,
        ):
            positions.append(
                {"line": line, "character": match.start(), "symbol": match.group()}
            )
    config = {
        "client": str(client),
        "codeql": _kernel.settings.CODEQL_BIN,
        "workspaces": search_paths(pack, _kernel=_kernel).split(os.pathsep),
        "documents": [{"path": str(source), "positions": positions[:8]}],
    }
    request = pack / "lsp-request.json"
    request.write_text(json.dumps(config))
    process = None
    try:
        process = subprocess.Popen(
            ["node", str(Path(__file__).with_name("lsp_probe.mjs")), str(request)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env={key: value for key, value in os.environ.items() if key in ENV_KEYS},
        )
        stdout, stderr = process.communicate(timeout=75)
        result = (
            json.loads(stdout)
            if process.returncode == 0
            else {"status": "failed", "reason": stderr[-2000:]}
        )
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        result = {"status": "failed", "reason": type(exc).__name__}
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
    if result.get("status") == "completed" and (
        not any(row.get("hover") for row in result.get("results", []))
    ):
        result["status"] = "no_evidence"
    result["author_commit"] = AUTHOR_COMMIT
    (pack / "lsp-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    return result
