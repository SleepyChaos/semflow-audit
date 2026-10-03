"""Bounded read-only LSP hover probe, absent tool is explicit unavailability."""

import json
import os
import re
import signal
import subprocess
from pathlib import Path

from app.adapters.codeql.custom import search_paths
from app.adapters.codeql.process import ENV_KEYS
from app.core.audit_config import ROOT, audit_settings

AUTHOR_COMMIT = "a33ea82bba156dc8352a0ecd85baff34cbb950ed"


def probe_types(pack):
    client = ROOT / "artifacts/codeql-lsp-mcp/dist/codeql-lsp-client.js"
    if not client.exists():
        return {
            "status": "unavailable",
            "reason": "Pinned author LSP client not installed",
        }
    source = pack / "generated.ql"
    positions = []
    for line, text in enumerate(source.read_text().splitlines()):
        for match in re.finditer(
            r"\b(?:Node|Expr|Call|CfgNode|CallCfgNode|ExprNode|getArg|getArgument|asExpr|asCfgNode|flow|isSource|isSink)\b",
            text,
        ):
            positions.append(
                {"line": line, "character": match.start(), "symbol": match.group()}
            )
    config = {
        "client": str(client),
        "codeql": audit_settings.CODEQL_BIN,
        "workspaces": search_paths(pack).split(os.pathsep),
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
        # Author client may leave/restart its Java child after an abrupt exit.
        # Always terminate the task-owned process group, never unrelated IDEs.
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
    if result.get("status") == "completed" and not any(
        row.get("hover") for row in result.get("results", [])
    ):
        result["status"] = "no_evidence"
    result["author_commit"] = AUTHOR_COMMIT
    (pack / "lsp-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    return result
