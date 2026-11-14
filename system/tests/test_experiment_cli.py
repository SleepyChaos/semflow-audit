"""CLI integration through real graphs and PostgreSQL, without paid tool calls."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4
from zipfile import ZipFile

import pytest
from app.cli.main import main
from app.contracts.experiments import ExperimentPlan
from app.core.db import engine
from app.persistence.stage_models import StageRun
from app.persistence.workspace import Workspace
from pydantic import ValidationError
from sqlmodel import Session

from tests.test_runtime_execution import EvidenceModel


def cli_context(context, monkeypatch):
    import app.runtime.stages as runtime
    from app.cli import experiments, records

    monkeypatch.setattr(
        experiments, "resolve_workspace", lambda session: Workspace(context["owner"])
    )
    monkeypatch.setattr(
        records, "resolve_workspace", lambda session: Workspace(context["owner"])
    )
    monkeypatch.setattr(runtime, "CompatibleModel", EvidenceModel)


def plan_file(context, samples, repetitions=1):
    path = context["root"] / "experiment.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "synthetic-cli-integration",
                "repetitions": repetitions,
                "samples": samples,
            }
        )
    )
    return path


def review_sample(context, name="sample"):
    return {
        "id": name,
        "audit_id": str(context["run_id"]),
        "stages": [
            {
                "kind": "review",
                "prompt_version": "1",
                "inputs": {"discover": False},
                "budget": {
                    "max_calls": 2,
                    "max_tokens": 5000,
                    "max_seconds": 60,
                    "model": "scripted-model",
                },
            }
        ],
    }


def test_batch_keeps_failures_repeats_and_independent_evidence(
    pipeline_context, monkeypatch, capsys
):
    ctx = pipeline_context
    cli_context(ctx, monkeypatch)
    bad = review_sample(ctx, "missing")
    bad["audit_id"] = str(uuid4())
    path = plan_file(ctx, [bad, review_sample(ctx)], repetitions=2)
    assert main(["batch", "--config", str(path)]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["total"] == 4 and result["counts"] == {"failed": 2, "completed": 2}
    assert len({row["run_id"] for row in result["runs"]}) == 4
    good = [row for row in result["runs"] if row["status"] == "completed"]
    assert len({row["stages"][0]["id"] for row in good}) == 2
    for row in result["runs"]:
        directory = Path(row["artifacts"])
        receipt = json.loads((directory / "execution-receipt.json").read_text())
        assert receipt["status"] == row["status"]
        frozen = json.loads((directory / "experiment-input.json").read_text())
        assert frozen["implementation"]["source_tree_sha256"]
        assert "runtime/stages.py" in frozen["implementation"]["source_files"]
        if row["status"] == "failed":
            assert row["not_evaluated_stages"] == 1 and not row["stages"]
        else:
            policy = row["stages"][0]["model_config_snapshot"]
            assert policy["execution_mode"] == "bounded" and policy["max_calls"] == 2
            assert policy["prompt_snapshot"]["purpose"] == "review"
            assert row["stages"][0]["usage"]["calls"] == 1
    identifier = good[0]["stages"][0]["id"]
    assert main(["inspect", "--run-id", identifier, "--evidence"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    candidate = inspected["candidates"][0]
    evidence = inspected["evidence"][0]
    assert candidate["stage_id"] == evidence["stage_id"] == identifier
    assert candidate["evidence_ids"] == [evidence["id"]]
    assert evidence["content"] == "value = eval(input())"
    assert main(["inspect", "--run-id", good[0]["run_id"]]) == 0
    assert json.loads(capsys.readouterr().out)["current_stages"][0]["id"] == identifier


def test_cli_zip_scan_failure_is_not_a_successful_empty_result(
    pipeline_context, monkeypatch, capsys
):
    from app.runtime import scans

    from tests.test_audit_core import document

    ctx = pipeline_context
    cli_context(ctx, monkeypatch)

    class Scanner:
        def version(self):
            return "scripted-scanner-not-CodeQL"

        def create_database(self, source, database, log, plan):
            database.mkdir()
            (database / "marker").write_text((source / "app.py").read_text())

        def analyze(self, database, sarif, log, plan):
            sarif.write_text(
                "{}"
                if "bad" in (database / "marker").read_text()
                else json.dumps(document([]))
            )

    monkeypatch.setattr(scans, "CodeQLScanner", Scanner)
    for name in ["bad", "good"]:
        with ZipFile(ctx["root"] / f"{name}.zip", "w") as archive:
            archive.writestr("app.py", f"# {name}\nprint(1)\n")
    path = plan_file(
        ctx,
        [
            {"id": "bad", "archive": "bad.zip", "stages": [{"kind": "review"}]},
            {"id": "good", "archive": "good.zip"},
        ],
    )
    assert main(["batch", "--config", str(path)]) == 1
    rows = json.loads(capsys.readouterr().out)["runs"]
    assert rows[0]["status"] == "failed" and rows[0]["scan"]["error"]
    assert rows[0]["not_evaluated_stages"] == 1 and rows[0]["stages"] == []
    assert rows[1]["status"] == "completed" and rows[1]["scan"]["findings"] == []
    assert rows[0]["audit_id"] != rows[1]["audit_id"]


def test_cli_run_selection_and_wrong_workspace(pipeline_context, monkeypatch, capsys):
    from app.cli import records

    ctx = pipeline_context
    cli_context(ctx, monkeypatch)
    path = plan_file(ctx, [review_sample(ctx, "first"), review_sample(ctx, "second")])
    assert main(["run", "--config", str(path)]) == 2
    capsys.readouterr()
    assert main(["run", "--config", str(path), "--sample", "second"]) == 0
    result = json.loads(capsys.readouterr().out)["runs"][0]
    assert result["sample_id"] == "second"
    monkeypatch.setattr(
        records, "resolve_workspace", lambda session: Workspace(uuid4())
    )
    for identifier in [result["run_id"], result["audit_id"], result["stages"][0]["id"]]:
        assert main(["inspect", "--run-id", identifier, "--evidence"]) == 2
        captured = capsys.readouterr()
        assert not captured.out and json.loads(captured.err)["error"] == "not_found"


def test_cli_retry_preserves_policy_and_original_failure(
    pipeline_context, monkeypatch, capsys
):
    ctx = pipeline_context
    cli_context(ctx, monkeypatch)
    path = plan_file(ctx, [review_sample(ctx)])
    assert main(["run", "--config", str(path)]) == 0
    original = json.loads(capsys.readouterr().out)["runs"][0]["stages"][0]
    with Session(engine) as session:
        row = session.get(StageRun, UUID(original["id"]))
        row.status, row.error = (
            "failed",
            "Synthetic failure after persisted model usage",
        )
        session.add(row)
        session.commit()
    assert main(["retry", "--run-id", original["id"]]) == 0
    retry = json.loads(capsys.readouterr().out)
    assert retry["id"] != original["id"] and retry["prompt_version"] == "1"
    assert retry["model_config_snapshot"] == original["model_config_snapshot"]
    with Session(engine) as session:
        assert session.get(StageRun, UUID(original["id"])).status == "failed"


def test_help_and_validation_do_not_import_web_queue_or_database(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps(
            {
                "name": "validate-only",
                "samples": [{"id": "one", "archive": "sample.zip"}],
            }
        )
    )
    code = """import sys
from app.cli.main import main
assert main(['validate', '--config', sys.argv[1]]) == 0
assert not {'app.main', 'app.jobs.celery_app', 'app.core.db'} & sys.modules.keys()
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(path)],
        env={**os.environ, "DATABASE_URL": "invalid-unused"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"] is True


@pytest.mark.parametrize(
    "change",
    [
        {"answer": "hidden-evaluator-label"},
        {"samples": [{"id": "one", "archive": "a.zip", "audit_id": str(uuid4())}]},
        {
            "samples": [
                {
                    "id": "one",
                    "archive": "a.zip",
                    "stages": [{"kind": "review", "inputs": {"unknown_flag": True}}],
                }
            ]
        },
    ],
)
def test_plan_rejects_labels_ambiguous_sources_and_unknown_options(change):
    from app.domain.audit import AuditError

    with pytest.raises((ValidationError, AuditError)):
        ExperimentPlan.model_validate(
            {
                "name": "invalid",
                "samples": [{"id": "one", "archive": "a.zip"}],
                **change,
            }
        )
