"""Concurrent attempt-1 validations must own different cleanup targets."""

import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

from semflow_research.adapters.repair.validator import validate_workspace


def test_validation_timeout_cannot_remove_another_executions_container(
    tmp_path, monkeypatch
):
    barrier = Barrier(2)
    names, cleaned = {}, []

    def run(args, **kwargs):
        if args[1:3] == ["image", "inspect"]:
            return SimpleNamespace(
                returncode=0, stdout="sha256:scripted-image", stderr=""
            )
        if args[1:3] == ["rm", "-f"]:
            cleaned.append(args[-1])
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        assert args[1] == "run"
        name = args[args.index("--name") + 1]
        mount = args[args.index("--mount") + 1]
        label = "timeout" if "/timeout/" in mount else "success"
        names[label] = name
        barrier.wait(5)
        if label == "timeout":
            raise subprocess.TimeoutExpired(args, 1)
        return SimpleNamespace(
            returncode=0, stdout="Scripted successful validation", stderr=""
        )

    monkeypatch.setattr(
        "semflow_research.adapters.repair.validator.subprocess.run", run
    )
    settings = SimpleNamespace(
        VALIDATOR_PYTHON_IMAGE="scripted-image", VALIDATOR_TIMEOUT=1
    )

    def validate(label):
        workspace = tmp_path / label / "attempt-1/workspace"
        workspace.mkdir(parents=True)
        (workspace / "app.py").write_text("value=1\n")
        return validate_workspace(
            workspace,
            "python",
            "syntax",
            _kernel=SimpleNamespace(settings=settings, execution_id=uuid4()),
        )

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(validate, ("timeout", "success")))
    assert names["timeout"] != names["success"]
    assert cleaned == [names["timeout"]]
    assert [result["status"] for result in results] == ["error", "passed"]
    assert results[0]["category"] == "environment"
