"""Build known test runtimes inside the dedicated daemon, never the host daemon."""

import os
import subprocess
from pathlib import Path

registry = os.environ.get("IMAGE_REGISTRY", "docker.io")
python_image = (
    f"{registry}/library/python:3.11-slim"
    "@sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9"
)
node_image = (
    f"{registry}/library/node:22.22.0-bookworm-slim"
    "@sha256:7cc56ef285a8568121537d17b05e72128f01b89c54607b51acf084a50ef483f3"
)
runners = Path(__file__).resolve().parents[1] / "runners"
commands = [
    [
        "build",
        "--platform=linux/amd64",
        "--build-arg",
        f"PYTHON_IMAGE={python_image}",
        "--tag",
        "ai-code-audit-validator:local",
        str(runners),
        "--file",
        str(runners / "Dockerfile.python"),
    ],
    ["pull", "--platform=linux/amd64", node_image],
    ["tag", node_image, "node:22-bookworm-slim"],
]
for command in commands:
    subprocess.run(["docker", *command], check=True)
print("Python/Flask and Node test runtimes are ready in the isolated daemon.")
