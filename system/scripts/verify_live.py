"""Exercise the real local API and CodeQL worker using a known vulnerable sample."""

import argparse
import json
import time
from pathlib import Path
from zipfile import ZipFile

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--language", choices=["python", "javascript"], default="python")
language = parser.parse_args().language
fixture = "vulnerable" if language == "python" else "vulnerable-js"
expected_rule = "py/code-injection" if language == "python" else "js/code-injection"

root = Path(__file__).resolve().parents[2]
client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=30)
archive = root / f"artifacts/verification-{language}.zip"
with ZipFile(archive, "w") as bundle:
    for file in (root / "system/tests/fixtures" / fixture).iterdir():
        bundle.write(file, file.name)
with archive.open("rb") as stream:
    response = client.post(
        "/api/v1/audits/",
        files={"file": ("sample.zip", stream)},
        data={"language": language, "project_name": "真实扫描验证"},
    )
response.raise_for_status()
identifier = response.json()["id"]
last = None
for _ in range(450):
    response = client.get(f"/api/v1/audits/{identifier}")
    response.raise_for_status()
    run = response.json()
    status = (run["status"], run["phase"])
    if status != last:
        print(
            json.dumps({"run_id": identifier, "status": status}, ensure_ascii=False),
            flush=True,
        )
        last = status
    if run["status"] in {"completed", "failed"}:
        break
    time.sleep(2)
else:
    raise RuntimeError("Verification deadline exceeded")
(root / f"artifacts/live-verification-{language}.json").write_text(
    json.dumps(run, ensure_ascii=False, indent=2)
)
assert run["status"] == "completed", run["error"]
assert any(f["rule"] == expected_rule for f in run["findings"]), (
    "Known vulnerability was not detected"
)
location = next(f for f in run["findings"] if f["rule"] == expected_rule)["locations"][
    0
]
source = client.get(
    f"/api/v1/audits/{identifier}/source",
    params={"file": location["file"], "line": location["line"]},
)
source.raise_for_status()
assert any("eval(" in line for line in source.json()["lines"])
assert client.get(f"/api/v1/audits/{identifier}/sarif").status_code == 200
assert httpx.get(f"http://127.0.0.1:8000/api/v1/audits/{identifier}").status_code == 200
print(
    json.dumps(
        {
            "verified": True,
            "findings": len(run["findings"]),
            "rule_ids": [f["rule"] for f in run["findings"]],
        }
    ),
    flush=True,
)
