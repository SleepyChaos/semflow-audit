from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from semflow_contracts.actions import (
    ApprovalRequest,
    ControlCommand,
    approval_subject_digest,
)
from semflow_contracts.errors import ResearchError
from semflow_contracts.evidence import ActorRef
from semflow_research.public.actions import approve
from semflow_research.runtime.approvals import validate_approval, validate_resume


def request(case):
    query = case.artifacts.commit(
        b"exact query", kind="query", schema_version="query/1"
    )
    fixtures = case.artifacts.commit(
        b"exact fixtures", kind="rule_fixtures", schema_version="fixtures/1"
    )
    checkpoint = case.artifacts.commit(
        b"exact checkpoint", kind="checkpoint", schema_version="checkpoint/1"
    )
    refs = (query, fixtures)
    return ApprovalRequest(
        action_id=uuid4(),
        kind="approve_rule_fixtures",
        execution_id=case.execution_id,
        checkpoint=checkpoint,
        subject_refs=refs,
        subject_digest=approval_subject_digest(refs),
        created_at=datetime.now(UTC),
    )


def test_approval_binds_both_query_and_fixtures_and_not_correctness(research_case):
    case = research_case
    pending = request(case)
    decision = approve(
        pending,
        actor=ActorRef(kind="human", id="operator"),
        approved=True,
        reason="Reviewed exact query and positive and negative fixtures",
    )
    assert validate_approval(
        pending, decision, artifacts=case.artifacts, checkpoint=pending.checkpoint
    )
    changed = case.artifacts.commit(
        b"changed fixture", kind="rule_fixtures", schema_version="fixtures/1"
    )
    refs = (pending.subject_refs[0], changed)
    revised = pending.model_copy(
        update={"subject_refs": refs, "subject_digest": approval_subject_digest(refs)}
    )
    with pytest.raises(ResearchError, match="another action or frozen subject"):
        validate_approval(
            revised, decision, artifacts=case.artifacts, checkpoint=pending.checkpoint
        )
    with pytest.raises(ValidationError, match="bind every frozen"):
        ApprovalRequest.model_validate(
            pending.model_dump(mode="json") | {"subject_digest": "0" * 64}
        )
    with pytest.raises(ValidationError, match="human"):
        approve(
            pending,
            actor=ActorRef(
                kind="experiment_fixture",
                id="fixture",
                provenance=pending.subject_refs[0],
            ),
            approved=True,
            reason="This fixture cannot impersonate human fixture approval",
        )


def test_stale_checkpoint_revision_and_modified_bytes_cannot_resume(research_case):
    from types import SimpleNamespace

    case = research_case
    pending = request(case)
    decision = approve(
        pending,
        actor=ActorRef(kind="human", id="operator"),
        approved=True,
        reason="Reviewed exact query and fixture bytes before resuming",
    )
    command = ControlCommand(
        command_id=uuid4(),
        execution_id=case.execution_id,
        action="resume",
        expected_revision=2,
        checkpoint_digest=pending.checkpoint.sha256,
        approval=decision,
        reason="Resume exact saved native graph",
    )
    result = SimpleNamespace(
        execution_status="awaiting_input",
        pending_action=pending,
        execution_id=case.execution_id,
    )
    assert validate_resume(
        command,
        result,
        revision=2,
        artifacts=case.artifacts,
        checkpoint=pending.checkpoint,
    )
    with pytest.raises(ResearchError, match="revision advanced"):
        validate_resume(
            command,
            result,
            revision=3,
            artifacts=case.artifacts,
            checkpoint=pending.checkpoint,
        )
    checkpoint = case.artifacts.commit(
        b"new checkpoint", kind="checkpoint", schema_version="checkpoint/1"
    )
    with pytest.raises(ResearchError, match="checkpoint identity"):
        validate_resume(
            command, result, revision=2, artifacts=case.artifacts, checkpoint=checkpoint
        )
    path = case.artifacts.root / str(case.execution_id) / pending.subject_refs[0].path
    path.write_bytes(b"modified query")
    with pytest.raises(ResearchError, match="Artifact bytes"):
        validate_resume(
            command,
            result,
            revision=2,
            artifacts=case.artifacts,
            checkpoint=pending.checkpoint,
        )


def test_rejection_and_predated_decision_are_explicit(research_case):
    case = research_case
    pending = request(case)
    rejected = approve(
        pending,
        actor=ActorRef(kind="human", id="operator"),
        approved=False,
        reason="Positive fixture is unrelated to the original target",
    )
    assert not validate_approval(
        pending, rejected, artifacts=case.artifacts, checkpoint=pending.checkpoint
    )
    predates = rejected.model_copy(
        update={"created_at": pending.created_at - timedelta(seconds=1)}
    )
    with pytest.raises(ResearchError, match="predates"):
        validate_approval(
            pending, predates, artifacts=case.artifacts, checkpoint=pending.checkpoint
        )
