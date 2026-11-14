"""External worker and Docker-transport substitutes, shared by entry-point tests."""

import os
import shutil
import sys
from pathlib import Path

from research.tests.openhands_cases import IMAGE

WORKER = """import json, sys, time
from pathlib import Path
from types import SimpleNamespace
from budget import install

config = json.load(sys.stdin)
directory = Path(config["directory"])
mode = MODE
class Metrics:
    def model_dump(self, **kwargs):
        return {"accumulated_token_usage": {"prompt_tokens": 30, "completion_tokens": 10}} if hasattr(self, "done") else {"accumulated_token_usage": None}
class Model:
    model = config["model"]
    metrics = Metrics()
    def generate(self, messages, *args, **kwargs):
        if mode in {"timeout", "cancel"}:
            time.sleep(30)
        self.metrics.done = True
        return "scripted response"
install(Model, directory, output_tokens=config["output_tokens"], timeout=10)
model = Model()
model.generate([{"text": "Inspect the authorized source"}])
if mode == "second_call":
    model.generate([{"text": "Second call must be rejected by the parent"}])
target = directory / "workspace/app.py"
target.write_text(target.read_text().replace("eval(input())", "int(input())"))
(directory / "events.jsonl").write_text('{"kind":"scripted_worker"}\\n')
(directory / "handoff-observed.json").write_text(json.dumps({key: config[key] for key in ["model", "base_url", "sdk_version", "timeout", "output_tokens", "max_steps", "prompt"]}))
(directory / "runtime-result.json").write_text(json.dumps({"status": "failed" if mode == "failed" else "completed", "error_type": "ScriptedFailure" if mode == "failed" else None, "sdk_version": "1.56.0", "metrics": {"accumulated_token_usage": {"prompt_tokens": 30, "completion_tokens": 10}}}))
"""


def resources(tmp_path, settings, monkeypatch, *, mode="success"):
    worker = tmp_path / "worker"
    worker.mkdir()
    worker.joinpath("runner.py").write_text("MODE = " + repr(mode) + "\n" + WORKER)
    assets = Path(__file__).parents[1] / "src/semflow_research/engines/openhands"
    for asset in ("budget.py", "container_tool.py"):
        shutil.copyfile(assets / asset, worker / asset)
    docker = tmp_path / "docker"
    docker.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$*\" >> '" + str(tmp_path / "docker.log") + "'\n"
    )
    docker.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    return settings.model_copy(
        update={
            "OPENHANDS_PYTHON": sys.executable,
            "OPENHANDS_IMAGE": IMAGE,
            "OPENHANDS_RUNNER": worker / "runner.py",
        }
    )
