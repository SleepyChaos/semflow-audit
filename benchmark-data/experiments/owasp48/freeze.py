"""Capture an executable app tree without secret contents or audit inputs."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts/research/owasp48/20261007-evolution"
parser = argparse.ArgumentParser()
parser.add_argument("version")
args = parser.parse_args()
target = OUT / "versions" / args.version
if target.exists():
    raise RuntimeError("Never overwrite an executable frozen version")
shutil.copytree(
    ROOT / "backend/app",
    target / "backend/app",
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
)
# Configuration is read by the application at runtime. No secret is copied to receipts.
(target / ".env").symlink_to(ROOT / ".env")
hashes = {
    str(p.relative_to(target / "backend/app")): hashlib.sha256(
        p.read_bytes()
    ).hexdigest()
    for p in (target / "backend/app").rglob("*")
    if p.is_file() and p.suffix in {".py", ".txt"}
}
(target / "identity.json").write_text(
    json.dumps(
        {"version": args.version, "hashes": hashes, "secret_content_archived": False},
        indent=2,
    )
)
print(json.dumps({"version": args.version, "production_files": len(hashes)}))
