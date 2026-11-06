"""Run a real, small discovery workflow through the Docker frontend's API."""

import argparse
import io
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4
from zipfile import ZipFile


def request(base: str, route: str, data=None, headers=None):
    with urlopen(Request(base + route, data=data, headers=headers or {}), timeout=30) as response:
        return json.load(response)


def upload(base: str):
    source = (
        "from flask import Flask, request\r\n"
        "app = Flask(__name__)\r\n\r\n"
        "@app.get('/calculate')\r\n"
        "def calculate():\r\n"
        "    return str(eval(request.args.get('expression', '0')))\r\n"
    )
    archive = io.BytesIO()
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("示例 项目/app.py", source)
        bundle.writestr("资料/说明.txt", "Synthetic compatibility fixture; never serve it.\n")
    boundary = "SemflowSmoke" + uuid4().hex
    name = "Windows Docker smoke " + uuid4().hex[:8]
    parts = []
    for key, value in (("language", "python"), ("project_name", name)):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    parts.extend([
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="兼容性 测试.zip"\r\nContent-Type: application/zip\r\n\r\n'.encode(),
        archive.getvalue(),
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    return request(base, "/api/v1/audits/", b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={boundary}"})


def run(base: str, timeout: int):
    environment = request(base, "/api/v1/audits/environment")
    if not all((environment.get("codeql_version"), environment.get("query_packs_present"), environment.get("queue_available"))):
        raise RuntimeError("CodeQL, both fixed query packs and Redis must be ready before this real-tools smoke test")
    audit = upload(base)
    identifier = audit["id"]
    print(json.dumps({"audit_id": identifier, "status": "submitted"}), flush=True)
    deadline = time.monotonic() + timeout
    while True:
        audit = request(base, f"/api/v1/audits/{identifier}")
        if audit["status"] in {"completed", "failed", "cancelled"}:
            break
        if time.monotonic() > deadline:
            raise TimeoutError(f"Audit {identifier} did not finish within {timeout}s; inspect its logs")
        time.sleep(3)
    dual = audit.get("coverage", {}).get("dual_engine", {})
    stages = request(base, f"/api/v1/audits/{identifier}/stages")
    scout = next((stage for stage in stages if stage["id"] == dual.get("scout_stage_id")), {})
    source = request(base, f"/api/v1/audits/{identifier}/source?" + urlencode({"file": "示例 项目/app.py"}))
    sarif = request(base, f"/api/v1/audits/{identifier}/sarif") if audit["status"] == "completed" else {}
    checks = {
        "audit_completed": audit["status"] == "completed",
        "both_branches_completed": dual.get("status") == "completed",
        "static_scan_completed": dual.get("codeql", {}).get("status") == "completed",
        "ai_scout_completed": scout.get("status") == "completed",
        "ai_called": scout.get("usage", {}).get("calls", 0) > 0,
        "unicode_source_readable": source.get("file") == "示例 项目/app.py" and any("eval(" in line for line in source.get("lines", [])),
        "sarif_downloadable": bool(sarif.get("runs")),
        "expected_rule_detected": any(row.get("rule") == "py/code-injection" for row in audit.get("findings", [])),
    }
    return {
        "passed": all(checks.values()), "audit_id": identifier,
        "audit_url": f"{base}/audits/{identifier}", "checks": checks,
        "codeql_version": audit.get("codeql_version"),
        "findings": len(audit.get("findings", [])),
        "ai_usage": scout.get("usage", {}),
        "static_error": dual.get("codeql", {}).get("error"),
        "scout_error": scout.get("error"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5174")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = run(args.base_url.rstrip("/"), args.timeout)
    except (HTTPError, URLError, OSError, ValueError, RuntimeError) as exc:
        result = {"passed": False, "error_type": type(exc).__name__, "error": str(exc)}
    rendered = json.dumps(result, ensure_ascii=True, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
