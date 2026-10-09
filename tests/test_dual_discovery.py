"""Discovery scope and failure isolation, using explicit model/scanner doubles."""

import json
from threading import Event
from types import SimpleNamespace

import pytest
from app.adapters.artifacts import ArtifactStore
from app.adapters.project_map import build_project_map
from app.contracts.scouting import ScoutRequest
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.audit_models import AuditRun
from app.persistence.audit_repository import AuditRepository
from app.persistence.stage_models import Candidate, StageRun
from app.persistence.stage_repository import StageRepository
from app.services.dual_scanning import DualScanService, ensure_scout_stage
from app.services.scouting import ScoutService
from app.workflows.dual_scanning import build_dual_scan_graph
from app.workflows.scouting import build_scout_graph
from sqlmodel import Session, select


class HypothesisModel:
    model = "explicit-scout-fixture"

    def __init__(self):
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        self.seen = []

    def generate(self, purpose, payload, schema):
        self.usage["calls"] += 1
        self.seen.append(payload)
        assert (
            purpose == "scout"
            and "static_alert" not in payload
            and "targets" not in payload
        )
        unit = payload["unit"]
        return schema.model_validate(
            {
                **(
                    {
                        "task_checks": [
                            {
                                "task_id": t["id"],
                                "status": "unknown",
                                "reason": "This fixture needs an upstream business guard contract.",
                                "evidence_ids": [],
                            }
                            for t in payload["inspection_tasks"]
                        ]
                    }
                    if "inspection_tasks" in payload
                    else {}
                ),
                "action": "final",
                "scope_summary": "Inspected this window, object ownership requires verification.",
                "findings": [
                    {
                        **(
                            {
                                "security_property": "object_ownership",
                                "operation_quote": payload["evidence"][0][
                                    "content"
                                ].splitlines()[0][:300],
                            }
                            if "security_property_contract" in payload
                            else {}
                        ),
                        "title": "Object ownership hypothesis",
                        "weakness": "CWE-639",
                        "primary_location": {
                            "file": unit["file"],
                            "line": unit["start_line"],
                        },
                        "security_condition": "A user should access only authorized objects.",
                        "observation": "The supplied window accesses the requested object.",
                        "missing_premises": [
                            "Does an upstream guard verify ownership?"
                        ],
                        "evidence_ids": [payload["evidence"][0]["id"]],
                    }
                ],
            }
        )


def run_scout(ctx, model=None, version="1", **inputs):
    with Session(engine) as db:
        stage = StageRun(
            audit_id=ctx["run_id"],
            kind="scout",
            prompt_version=version,
            inputs=ScoutRequest(**inputs).model_dump(mode="json"),
        )
        db.add(stage)
        db.commit()
        db.refresh(stage)
        identifier = str(stage.id)
    StageRepository().claim(identifier)
    service = ScoutService(identifier, model or HypothesisModel())
    build_scout_graph(service).invoke({"stage_id": identifier})
    return service


@pytest.mark.parametrize(
    "pipeline_context",
    [
        {
            "orders/lookup.py": "def lookup(record_id):\n    return store[record_id]\n",
            "auth/check.py": "def authorized(user):\n    return user.active\n",
        }
    ],
    indirect=True,
)
def test_scout_inspects_unanchored_modules_without_static_alerts(pipeline_context):
    ctx = pipeline_context
    model = HypothesisModel()
    service = run_scout(ctx, model)
    result = service.repository.get(service.stage_id).result
    assert result["coverage"]["inspected_windows"] == 2
    assert {p["unit"]["file"] for p in model.seen} == {
        "orders/lookup.py",
        "auth/check.py",
    }
    with Session(engine) as db:
        rows = db.exec(
            select(Candidate).where(Candidate.stage_id == service.stage.id)
        ).all()
    assert len(rows) == 2 and all(
        r.status == "pending" and r.novelty == "unverified" for r in rows
    )
    assert all(u["hypotheses"][0]["missing_premises"] for u in result["units"])
    # Completed units replay without another provider call or duplicate candidates.
    build_scout_graph(service).invoke({"stage_id": service.stage_id})
    assert model.usage["calls"] == 2


@pytest.mark.parametrize(
    "pipeline_context",
    [{"a/long.py": "value = 1\n" * 240, "b/other.py": "value = 2\n"}],
    indirect=True,
)
def test_window_round_robin_and_uninspected_coverage(pipeline_context):
    service = run_scout(pipeline_context, max_units=2)
    project = json.loads((service.directory / "scout-map.json").read_text())
    assert [u["file"] for u in project["units"][:2]] == ["a/long.py", "b/other.py"]
    coverage = service.repository.get(service.stage_id).result["coverage"]
    assert coverage["planned_windows"] == 4 and coverage["inspected_windows"] == 2
    assert coverage["status"] == "partial" and coverage["uninspected_windows"] == 2


def test_scout_invalid_location_is_incomplete_not_safe(pipeline_context):
    class Invented(HypothesisModel):
        def generate(self, purpose, payload, schema):
            row = super().generate(purpose, payload, schema)
            row.findings[0].primary_location.line = 500
            return row

    service = run_scout(pipeline_context, Invented())
    result = service.repository.get(service.stage_id).result
    assert result["coverage"]["inspected_windows"] == 0
    assert result["units"][0]["status"] == "incomplete"
    with Session(engine) as db:
        assert not db.exec(
            select(Candidate).where(Candidate.stage_id == service.stage.id)
        ).all()


def test_scout_budget_and_map_tamper_preserve_unknown(pipeline_context):
    class Exhausted(HypothesisModel):
        def generate(self, *_):
            raise AuditError("model budget exhausted", code="budget_exhausted")

    service = run_scout(pipeline_context, Exhausted())
    assert (
        service.repository.get(service.stage_id).result["coverage"]["stop_reason"]
        == "budget_exhausted"
    )
    project = json.loads((service.directory / "scout-map.json").read_text())
    project["files"][0]["lines"] = 999
    (service.directory / "scout-map.json").write_text(json.dumps(project))
    with pytest.raises(AuditError, match="修改"):
        service.prepare({})


def test_parallel_graph_waits_for_both_branches(tmp_path):
    codeql_started, scout_started = Event(), Event()
    joined = []

    class Service:
        artifacts = SimpleNamespace(directory=lambda _: tmp_path)

        def codeql(self, _):
            codeql_started.set()
            assert scout_started.wait(3)
            return {"codeql_outcome": {"status": "failed"}}

        def scout(self, _):
            scout_started.set()
            assert codeql_started.wait(3)
            return {"scout_outcome": {"status": "completed"}}

        def join(self, state):
            assert state["codeql_outcome"]["status"] == "failed"
            assert state["scout_outcome"]["status"] == "completed"
            joined.append(True)
            return {"joined": True}

    assert build_dual_scan_graph(Service()).invoke({"run_id": "parallel"})["joined"]
    assert joined == [True]


def test_codeql_failure_preserves_scout_and_allows_scoped_review(pipeline_context):
    ctx = pipeline_context
    with Session(engine) as db:
        run = db.get(AuditRun, ctx["run_id"])
        run.status = "running"
        run.findings = []
        db.add(run)
        db.commit()

    class FailingScanner:
        repository, artifacts = AuditRepository(), ArtifactStore()

        def create_database(self, _):
            raise AuditError("Actual extraction failed")

    service = DualScanService(FailingScanner(), HypothesisModel)
    result = build_dual_scan_graph(service).invoke({"run_id": str(ctx["run_id"])})
    run = AuditRepository().get(str(ctx["run_id"]))
    assert result["joined"] and run.status == "failed" and "extraction" in run.error
    assert run.coverage["dual_engine"]["scout"]["status"] == "completed"
    assert run.coverage["dual_engine"]["review_ready"]
    stage_id = run.coverage["dual_engine"]["scout_stage_id"]
    assert ensure_scout_stage(str(ctx["run_id"])) == stage_id
    assert StageRepository().get(stage_id).prompt_version == "7"
    assert StageRepository().get(stage_id).result["units"][0]["hypotheses"]


def test_map_oversized_line_is_explicit_gap(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    path = root / "oversized.py"
    path.write_text("x" * 13000 + "\nvalue = 1\n")
    fake = SimpleNamespace(
        root=root,
        files=lambda: [path],
        allowed=lambda _: path,
        audit=SimpleNamespace(snapshot_hash="s", language="python"),
    )
    project = build_project_map(fake, 100)
    assert project["skipped"][0]["reason"] == "oversized_source_line"
    assert project["units"][0]["start_line"] == 2
