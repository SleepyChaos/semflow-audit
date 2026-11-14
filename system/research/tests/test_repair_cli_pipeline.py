"""All native repair CLI operations execute in fresh processes with platform imports forbidden."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from research.tests.native_cases import repair_spec
from research.tests.repair_cli_cases import SCRIPT


def test_cli_build_generate_verify_share_core_without_platform(
    research_case, settings, tmp_path
):
    system = Path(__file__).resolve().parents[2]
    environment = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("AI_", "DATABASE_", "REDIS_", "PROJECT_"))
    }
    environment["PYTHONPATH"] = os.pathsep.join(
        str(system / p / "src") for p in ("contracts", "research", "research_cli")
    )
    environment["HAYSTACK_TELEMETRY_ENABLED"] = "false"
    original = repair_spec(research_case).model_dump(mode="json")
    values = settings.model_dump(mode="json")
    for name in ("AI_BASE_URL", "AI_MODEL", "AI_API_KEY", "ARTIFACT_ROOT"):
        values.pop(name, None)
    resources = tmp_path / "resources.json"
    resources.write_text(
        json.dumps(
            {
                "profile_id": original["policy"]["resource_profile"],
                "settings": values,
                "model_endpoints": {
                    original["model"]["endpoint_profile"]: {
                        "base_url": "http://scripted.invalid"
                    }
                },
            }
        )
    )

    def cli(value):
        path = tmp_path / (value["operation"] + ".json")
        path.write_text(json.dumps(value))
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                SCRIPT,
                "run",
                "--spec",
                str(path),
                "--resources",
                str(resources),
                "--root",
                str(research_case.ledger.root),
            ],
            env=environment,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        return json.loads(result.stdout)

    behavior = research_case.artifacts.commit(
        b"Preserve integer inputs and reject expressions",
        kind="materials",
        schema_version="semflow.requested-behavior/1",
        media_type="text/plain",
    )
    build = json.loads(json.dumps(original))
    build.update(
        execution_id=str(uuid4()),
        operation="build_suite",
        inputs={
            "targets": original["inputs"]["targets"],
            "requested_behavior": behavior.model_dump(mode="json"),
            "runtime_profile": original["policy"]["resource_profile"],
        },
    )
    build["implementation"]["method_version"] = "2"
    build["prompts"][0].update(role="verification_suite", version="2")
    suite = cli(build)["result"]["suite"]
    original["inputs"].update(suite=suite)
    original["inputs"]["method_policy"].update(
        selected_suite_feedback=True, baseline_reuse=True
    )
    original["inputs"]["validation_plan"]["before_after"] = True
    generated = cli(original)
    assert generated["result"]["outcome"] == "checks_passed"
    verify = json.loads(json.dumps(original))
    verify.update(
        execution_id=str(uuid4()),
        operation="verify",
        model=None,
        prompts=[],
        inputs={
            "repair": {
                "execution_id": original["execution_id"],
                "entity_id": generated["result"]["repair_id"],
                "bundle": generated["manifest"],
            },
            "patch": generated["result"]["patch"],
            "patched_source": generated["result"]["patched_source"],
            "suite": suite,
            "validation_plan": {"syntax": False, "before_after": True},
        },
    )
    verify["implementation"]["method_version"] = "1"
    compared = cli(verify)
    assert compared["result"]["receipt"]["status"] == "passed"
    assert compared["usage"]["calls"] == 0
