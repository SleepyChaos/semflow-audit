"""Install fixed query packs and their exact library sources into the image."""

import subprocess
from pathlib import Path

import yaml

packs = Path("/opt/packs")
specifications = ["codeql/python-queries@1.6.0", "codeql/javascript-queries@1.4.0"]
subprocess.run(
    ["codeql", "pack", "download", "--dir", str(packs), *specifications], check=True
)
dependencies = set()
for lock in packs.glob("codeql/*-queries/*/codeql-pack.lock.yml"):
    for name, value in yaml.safe_load(lock.read_text())["dependencies"].items():
        dependencies.add(f"{name}@{value['version']}")
if not dependencies:
    raise RuntimeError("Query pack dependency locks were not installed")
subprocess.run(
    [
        "codeql",
        "pack",
        "download",
        "--force",
        "--dir",
        str(packs),
        *sorted(dependencies),
    ],
    check=True,
)
