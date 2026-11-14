"""Opt-in: pinned real SDK and networkless Docker; only the model is scripted."""

import json
import os
import shutil
from pathlib import Path

import pytest
from semflow_research.adapters.repair.openhands_receipts import read
from semflow_research.public.repair import execute
from semflow_research.public.runtime import prepare
from semflow_research.runtime.repair_outputs import read_attempts

from research.tests.openhands_cases import openhands_spec
from research.tests.openhands_sdk_cases import sdk_resources


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("AUDIT_RUN_REAL_TOOLS") != "1",
    reason="Explicit real SDK/Docker opt-in",
)
def test_real_pinned_sdk_networkless_sandbox_and_durable_call_budget(
    research_case, settings, repair_model, monkeypatch, tmp_path
):
    settings = sdk_resources(settings, tmp_path)
    image = settings.OPENHANDS_IMAGE
    from semflow_research.adapters.repair.validator import validate_workspace

    monkeypatch.setattr(
        "semflow_research.repair.repair.validate_workspace", validate_workspace
    )
    spec = openhands_spec(research_case)
    value = spec.model_dump(mode="json")
    value["inputs"]["openhands"].update(image_digest=image, timeout_seconds=60)
    import hashlib

    from semflow_contracts.runs import validate_spec
    from semflow_research.public.implementation import code_digest

    value["implementation"]["code_digest"] = code_digest()
    value["implementation"]["dependency_lock_digest"] = hashlib.sha256(
        (Path(__file__).resolve().parents[2] / "uv.lock").read_bytes()
    ).hexdigest()

    spec = validate_spec(value)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    destination = os.environ.get("SEMFLOW_RESEARCH_GATE_REPORT")
    if destination:
        target = Path(destination) / str(spec.execution_id)
        shutil.copytree(research_case.ledger.root, target / "research")
        (target / "result.json").write_text(result.model_dump_json(indent=2))
        (target / "scope.json").write_text(
            json.dumps(
                {
                    "sdk": "1.56.0",
                    "docker_image": image,
                    "scope": "Synthetic one-file project; real SDK, sandbox, syntax and journal. Semantic and SDK model providers are scripted; not a model-quality claim.",
                },
                indent=2,
            )
        )
    assert result.execution_status == "completed", result.failure
    assert result.result.outcome == "checks_passed"
    attempts = read_attempts(
        context.artifacts,
        result.result.attempts,
        execution_id=spec.execution_id,
        snapshot_id=spec.source.snapshot_id,
    )
    engine = read(
        context.artifacts,
        attempts.records[0].engine_receipt,
        execution_id=spec.execution_id,
    )
    assert engine.status == "completed"
    runtime = json.loads(context.artifacts.read(engine.files["runtime-result.json"]))
    assert runtime["sdk_version"] == "1.56.0" and runtime["event_count"] > 0
    external = [
        entry
        for entry in result.usage.by_provider
        if entry.provider.startswith("openhands/")
    ]
    assert (
        len(external) == 1
        and external[0].calls == 2
        and external[0].input_tokens == 200
    )
    assert result.usage.calls == 4 and result.usage.completeness == "complete"
    assert (
        context.source_root.joinpath("app.py").read_text() == "value = eval(input())\n"
    )
