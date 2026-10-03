import pytest
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.stage_models import Evidence, StageRun
from app.services.review import ReviewService
from sqlmodel import Session

from tests.model_fixtures import ScriptedModel


def service(context):
    with Session(engine) as db:
        stage = StageRun(audit_id=context["run_id"], kind="review")
        db.add(stage)
        db.commit()
        db.refresh(stage)
        return ReviewService(str(stage.id), ScriptedModel())


def test_repeated_evidence_deduplicates_context_but_preserves_tool_trace(
    pipeline_context,
):
    review = service(pipeline_context)
    state = review.prepare()
    initial = state["context"]["evidence"][0]
    state["response"] = {
        "tool": {
            "name": "read_source",
            "arguments": {"file": "app.py", "start_line": 1, "end_line": 13},
        }
    }
    state.update(review.gather(state))
    state.update(review.gather(state))
    assert len(state["context"]["evidence"]) == 1
    assert len(state["context"]["tool_trace"]) == 2
    assert all(
        t["evidence_id"] == initial["id"] for t in state["context"]["tool_trace"]
    )
    other = service(pipeline_context)
    assert other.evidence.read("app.py", 1, 13)["id"] != initial["id"]


def test_same_content_different_reference_cannot_reuse_identity(pipeline_context):
    review = service(pipeline_context)
    first = review.evidence.record("search", "[]", {"term": "first"})
    second = review.evidence.record("search", "[]", {"term": "second"})
    assert first["id"] != second["id"]


def test_modified_cached_evidence_is_rejected(pipeline_context):
    from uuid import UUID

    review = service(pipeline_context)
    first = review.evidence.read("app.py")
    with Session(engine) as db:
        row = db.get(Evidence, UUID(first["id"]))
        row.content = "modified"
        db.add(row)
        db.commit()
    with pytest.raises(AuditError, match="被修改"):
        review.evidence.read("app.py")
