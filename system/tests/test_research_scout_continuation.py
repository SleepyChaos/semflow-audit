"""A new Web continuation reuses frozen windows and the same research algorithm."""

import shutil

from app.main import app
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, StageRun
from app.research_bridge.models import ResearchBinding
from app.research_bridge.requests import research_root
from app.runtime.stages import run_stage
from app.services.scout_continuation import continuation_inputs
from app.services.stage_lifecycle import create_stage_run
from fastapi.testclient import TestClient
from semflow_research.public.discovery_results import read_result
from sqlmodel import Session, select

from tests.research_bridge_cases import CurrentScoutModel


def test_new_continuation_reads_frozen_map_and_preserves_prior_candidate_ids(
    bridge_case,
):
    from app.adapters.snapshot import snapshot_digest

    db, owner, audit_id, source = bridge_case
    (source / "second.py").write_text("answer = int(input())\n")
    with Session(db) as session:
        audit = session.get(AuditRun, audit_id)
        audit.snapshot_hash = snapshot_digest(source)
        session.add(audit)
        session.commit()
        first = create_stage_run(
            session, audit.id, owner, "scout", {"max_units": 1, "steps_per_unit": 1}
        )
    first_result = run_stage(str(first.id), kernel_model_factory=CurrentScoutModel)
    assert first_result.status == "completed", first_result.error
    assert first_result.result["coverage"]["continuable_windows"] > 0
    with Session(db) as session:
        first_binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == first.id)
        ).one()
        parent_execution = first_binding.execution_id
        old_candidates = session.exec(
            select(Candidate).where(Candidate.stage_id == first.id)
        ).all()
        old_ids = {row.id for row in old_candidates}
        for row in old_candidates:
            row.status = (
                "confirmed"  # Platform human decision is preserved by projection.
            )
            session.add(row)
        session.commit()
    # The platform view remains for the old API; the algorithm must use frozen
    # refs and must not need the producer's mutable research workspace.
    shutil.rmtree(research_root() / "workspaces" / str(parent_execution))
    with Session(db) as session:
        previous = session.get(StageRun, first.id)
        audit = session.get(AuditRun, audit_id)
        inputs, initial = continuation_inputs(previous, audit, session)
        second = create_stage_run(
            session,
            audit_id,
            owner,
            "scout",
            inputs,
            initial_result=initial,
            prompt_version=previous.prompt_version,
            policy=previous.model_config_snapshot,
        )

    class PendingModel(CurrentScoutModel):
        def generate(self, purpose, payload, schema):
            self.usage["calls"] += 1
            assert payload["unit"]["file"] == "second.py"
            return schema.model_validate(
                {
                    "action": "final",
                    "scope_summary": "The remaining numeric conversion source was read",
                    "findings": [],
                    "task_checks": [
                        {
                            "task_id": task["id"],
                            "status": "unknown",
                            "conclusion": "unknown",
                            "reason": "The source was read; no whole-project safety conclusion is made",
                            "evidence_ids": [],
                        }
                        for task in payload["inspection_tasks"]
                    ],
                    "route_checks": [],
                }
            )

    final = run_stage(str(second.id), kernel_model_factory=PendingModel)
    assert final.status == "completed", final.error
    assert final.result["coverage"]["inspected_windows"] == 2
    assert final.result["continuation"]["inherited_windows"] == 1
    with Session(db) as session:
        second_binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == second.id)
        ).one()
        native = read_result(second_binding.execution_id, root=research_root())
        assert {row.execution_id for row in native.candidates} == {parent_execution}
        assert {row.id for row in session.exec(select(Candidate)).all()} == old_ids
        assert all(
            row.status == "confirmed" for row in session.exec(select(Candidate)).all()
        )
    with TestClient(app) as client:
        assert client.get(f"/api/v1/stages/{second.id}/materials").status_code == 200
        assert len(client.get(f"/api/v1/audits/{audit_id}/candidates").json()) == 1
