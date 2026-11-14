"""Fresh CLI processes with substitutions only at external model/CodeQL boundaries."""

import json
import os
import subprocess
import sys
from pathlib import Path

from research.tests.rule_cases import rule_spec

SCRIPT = r"""
import importlib.abc, json, os, sys
from pathlib import Path
class NoPlatform(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'app','fastapi','celery','sqlmodel','pydantic_settings'}:
            raise RuntimeError('Forbidden platform import: '+fullname)
sys.meta_path.insert(0, NoPlatform())
from pytest import MonkeyPatch
from rule_cases import install_substitutes
from semflow_cli.main import main
from semflow_research.adapters.ai import provider
phases = []
with MonkeyPatch.context() as patch:
    install_substitutes(patch, phases, real_tools=os.environ.get('SEMFLOW_RULE_CLI_REAL_TOOLS') == '1')
    if os.environ.get('SEMFLOW_RULE_CLI_REPLAY') == '1':
        from rule_replay_cases import install_replay
        install_replay(patch, phases)
    original = provider.OpenAI
    def client(**kw):
        assert kw['api_key'] == os.environ['SEMFLOW_RULE_CLI_TEST_KEY']
        return original(**kw)
    patch.setattr(provider, 'OpenAI', client)
    code = main(sys.argv[1:])
Path(os.environ['SEMFLOW_RULE_CLI_PHASES']).write_text(json.dumps(phases))
raise SystemExit(code)
"""


def inputs(case, settings, tmp_path, *, holdout):
    base = rule_spec(case, settings)
    documents = [
        {
            "collection": collection,
            "title": collection,
            "source": "cli-fixture:" + collection,
            "language": "python",
            "chunks": ["CodeQL eval reference and examples"],
            "provenance": {
                "api_version": "test",
                "validation": {"status": "passed", "kind": "compile_only"},
            },
        }
        for collection in ("reference", "rule_example")
    ]
    options = {
        "requirement": "Observe direct eval dynamic calls for review",
        "purpose": "review_anchor",
        "strategy": "new_query",
        "source_paths": ["app.py"],
        "model": base.model.model_dump(mode="json"),
        "policy": base.policy.model_dump(mode="json"),
        "retrieval": base.inputs.retrieval.model_dump(mode="json"),
        "generation": base.inputs.generation.model_dump(mode="json"),
        "development": {"compile": True, "project_replay": False},
        "acceptance": {
            "fixture_validation": True,
            "holdout_id": "python-eval-review_anchor-v1" if holdout else None,
        },
    }
    options_path, documents_path = (
        tmp_path / "options.json",
        tmp_path / "documents.json",
    )
    options_path.write_text(json.dumps(options))
    documents_path.write_text(json.dumps(documents))
    resource_path = tmp_path / "explicit-resources.json"
    resource_values = settings.model_dump(mode="json")
    for name in ("AI_BASE_URL", "AI_MODEL", "AI_API_KEY", "ARTIFACT_ROOT"):
        resource_values.pop(name, None)
    resource_path.write_text(
        json.dumps(
            {
                "profile_id": base.policy.resource_profile,
                "settings": resource_values,
                "model_endpoints": {
                    base.model.endpoint_profile: {
                        "base_url": settings.AI_BASE_URL,
                        "api_key_env": "SEMFLOW_RULE_CLI_TEST_KEY",
                    }
                },
            }
        )
    )
    system = Path(__file__).resolve().parents[2]
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("AI_", "DATABASE_", "REDIS_", "PROJECT_"))
    }
    env.update(
        PYTHONPATH=os.pathsep.join(
            str(system / name)
            for name in (
                "contracts/src",
                "research/src",
                "research_cli/src",
                "research/tests",
            )
        ),
        SEMFLOW_RULE_CLI_TEST_KEY="explicit-synthetic-test-credential",
        SEMFLOW_RULE_CLI_PHASES=str(tmp_path / "phases.json"),
    )
    args = [
        "rule-generate",
        "--root",
        str(case.ledger.root),
        "--source-directory",
        str(case.source),
        "--documents",
        str(documents_path),
        "--options",
        str(options_path),
        "--resources",
        str(resource_path),
        "--dependency-lock",
        str(system / "uv.lock"),
    ]
    return env, args, resource_path


def cli(env, arguments, tmp_path, *, timeout=45):
    completed = subprocess.run(
        [sys.executable, "-c", SCRIPT, *arguments],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    phases = json.loads(Path(env["SEMFLOW_RULE_CLI_PHASES"]).read_bytes())
    return completed, phases
