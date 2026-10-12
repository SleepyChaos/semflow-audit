from uuid import UUID, uuid4
import pytest
from sqlmodel import Session, select
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.stage_models import Candidate, StageRun
from app.persistence.stage_repository import StageRepository
from app.services.review import ReviewService
from app.workflows.review import build_review_graph
from tests.model_fixtures import ScriptedModel


def execute_review(context, provider=None, inputs=None):
    with Session(engine) as session:
        stage = StageRun(
            audit_id=context["run_id"], kind="review", inputs=inputs or {"max_steps": 8}
        )
        session.add(stage)
        session.commit()
        session.refresh(stage)
        identifier = str(stage.id)
    StageRepository().claim(identifier)
    service = ReviewService(identifier, provider or ScriptedModel())
    build_review_graph(service).invoke({"stage_id": identifier})
    return identifier


def test_model_recommendation_needs_human_confirmation_and_report(pipeline_context):
    ctx = pipeline_context
    execute_review(ctx)
    api = ctx["client"]
    candidates = api.get(f"/api/v1/audits/{ctx['run_id']}/candidates").json()
    assert candidates[0]["status"] == "pending"
    report = api.get(f"/api/v1/audits/{ctx['run_id']}/report").json()
    assert report["summary"]["candidate_states"]["confirmed"] == 0
    candidate = candidates[0]
    response = api.post(
        f"/api/v1/candidates/{candidate['id']}/decisions",
        json={
            "status": "confirmed",
            "reason": "Manually checked input reaches dynamic execution without protection.",
            "evidence_ids": candidate["evidence_ids"],
        },
    )
    assert response.status_code == 201
    report = api.get(f"/api/v1/audits/{ctx['run_id']}/report").json()
    assert report["summary"]["candidate_states"]["confirmed"] == 1
    assert report["summary"]["confirmed_ai_discoveries"] == 0
    assert len(report["decisions"]) == 1
    # A raw record is exportable, but a Chinese AI report requires genuine generation.
    assert api.get(f"/api/v1/audits/{ctx['run_id']}/report.md").status_code == 409
    assert report["ai_report"]["status"] == "missing"


def test_invented_evidence_is_rejected(pipeline_context):
    class Invented(ScriptedModel):
        def generate(self, purpose, payload, schema):
            return schema.model_validate(
                {
                    "action": "final",
                    "findings": [
                        {
                            "candidate_id": payload["targets"][0]["candidate_id"],
                            "title": "Invented",
                            "description": "This unsupported conclusion must never be accepted.",
                            "assessment": "supported",
                            "evidence_ids": [str(uuid4())],
                        }
                    ],
                }
            )

    with pytest.raises(AuditError, match="未取到"):
        execute_review(pipeline_context, Invented())
    with Session(engine) as session:
        rows = session.exec(
            select(Candidate).where(Candidate.audit_id == pipeline_context["run_id"])
        ).all()
        assert all(row.status == "pending" for row in rows)


def test_budget_exhaustion_is_failure_not_exclusion(pipeline_context):
    with pytest.raises(AuditError, match="预算耗尽"):
        execute_review(pipeline_context, ScriptedModel(), {"max_steps": 1})


def test_cross_task_evidence_cannot_confirm(pipeline_context):
    execute_review(pipeline_context)
    api = pipeline_context["client"]
    candidate = api.get(
        f"/api/v1/audits/{pipeline_context['run_id']}/candidates"
    ).json()[0]
    result = api.post(
        f"/api/v1/candidates/{candidate['id']}/decisions",
        json={
            "status": "confirmed",
            "reason": "Invalid evidence must not change state.",
            "evidence_ids": [str(uuid4())],
        },
    )
    assert result.status_code == 422
    assert (
        api.get(f"/api/v1/audits/{pipeline_context['run_id']}/candidates").json()[0][
            "status"
        ]
        == "pending"
    )


def test_pending_candidate_cannot_enter_repair(pipeline_context):
    execute_review(pipeline_context)
    api = pipeline_context["client"]
    candidate = api.get(
        f"/api/v1/audits/{pipeline_context['run_id']}/candidates"
    ).json()[0]
    assert (
        api.post(
            f"/api/v1/audits/{pipeline_context['run_id']}/repair",
            json={"candidate_ids": [candidate["id"]]},
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "value = eval(input())\nother = eval(input())\n"}],
    indirect=True,
)
def test_new_candidate_location_is_grounded_and_counted_once(pipeline_context):
    class Novel(ScriptedModel):
        def generate(self, purpose, payload, schema):
            return schema.model_validate(
                {
                    "action": "final",
                    "findings": [
                        {
                            "title": "Additional dynamic execution",
                            "description": "A separately located dynamic execution operation needs confirmation.",
                            "assessment": "supported",
                            "evidence_ids": [
                                row["id"]
                                for row in payload["evidence"]
                                if row["kind"] == "code"
                            ],
                            "weakness": "CWE-095",
                            "primary_location": {"file": "app.py", "line": 2},
                            "related_target": "app.py:2",
                        }
                    ],
                }
            )

    api = pipeline_context["client"]
    for _ in range(2):
        execute_review(pipeline_context, Novel())
        rows = api.get(f"/api/v1/audits/{pipeline_context['run_id']}/candidates").json()
        novel = next(row for row in reversed(rows) if row["origin"] == "ai")
        assert novel["novelty"] == "new_location"
        assert (
            api.post(
                f"/api/v1/candidates/{novel['id']}/decisions",
                json={
                    "status": "confirmed",
                    "reason": "Manually verified a separate source operation at line two.",
                    "evidence_ids": novel["evidence_ids"],
                },
            ).status_code
            == 201
        )
    report = api.get(f"/api/v1/audits/{pipeline_context['run_id']}/report").json()
    assert report["summary"]["confirmed_ai_discoveries"] == 1
    assert len([row for row in report["candidates"] if row["origin"] == "ai"]) == 2


def test_ai_overlap_is_not_counted_as_incremental_gain(pipeline_context):
    class Overlap(ScriptedModel):
        def generate(self, purpose, payload, schema):
            return schema.model_validate(
                {
                    "action": "final",
                    "findings": [
                        {
                            "title": "Same dynamic execution",
                            "description": "This repeats a static alert location rather than a new discovery.",
                            "assessment": "supported",
                            "evidence_ids": [row["id"] for row in payload["evidence"]],
                            "primary_location": {"file": "app.py", "line": 1},
                            "related_target": "app.py:1",
                        }
                    ],
                }
            )

    execute_review(pipeline_context, Overlap())
    api = pipeline_context["client"]
    candidate = next(
        row
        for row in api.get(
            f"/api/v1/audits/{pipeline_context['run_id']}/candidates"
        ).json()
        if row["origin"] == "ai"
    )
    assert candidate["novelty"] == "overlaps_static"
    api.post(
        f"/api/v1/candidates/{candidate['id']}/decisions",
        json={
            "status": "confirmed",
            "reason": "Manually verified this overlaps the pre-existing static alert.",
            "evidence_ids": candidate["evidence_ids"],
        },
    )
    report = api.get(f"/api/v1/audits/{pipeline_context['run_id']}/report").json()
    assert report["summary"]["confirmed_ai_discoveries"] == 0


def test_modified_snapshot_cannot_be_used_as_original_evidence(pipeline_context):
    from app.adapters.artifacts import ArtifactStore
    from app.services.evidence import EvidenceService

    root = ArtifactStore().source(str(pipeline_context["run_id"]))
    (root / "app.py").write_text("value = 0\n")
    with pytest.raises(AuditError, match="完整性"):
        EvidenceService(str(pipeline_context["run_id"]), str(uuid4()), [])
