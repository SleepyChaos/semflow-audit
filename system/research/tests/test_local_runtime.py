from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from semflow_contracts.errors import ResearchError
from semflow_contracts.events import EventInput, PhasePayload
from semflow_contracts.runs import validate_spec
from semflow_research.runtime.artifacts import LocalArtifacts
from semflow_research.runtime.ledger import LocalLedger


def test_claim_is_exclusive_and_input_id_is_immutable(research_case):
    case = research_case
    changed = case.spec.model_dump(mode="json")
    changed["policy"]["max_calls"] += 1
    with pytest.raises(ResearchError, match="different inputs"):
        case.ledger.create(validate_spec(changed))
    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = list(
            pool.map(case.ledger.claim, [case.execution_id, case.execution_id])
        )
    assert sorted(claimed) == [False, True]
    assert len(case.ledger.events(case.execution_id)) == 1


def test_failure_receipt_survives_restart_without_becoming_empty_success(research_case):
    case = research_case
    assert case.ledger.claim(case.execution_id)
    published = case.ledger.publish(case.failed_result(), expected_revision=0)
    restored = LocalLedger(case.ledger.root).inspect(case.execution_id)
    assert restored == published
    assert (
        restored.execution_status == "failed"
        and restored.failure.code == "parse_failed"
    )
    assert restored.result is None and restored.manifest.sha256
    with pytest.raises(ResearchError, match="immutable"):
        case.ledger.publish(case.failed_result(), expected_revision=1)
    assert len(case.ledger.events(case.execution_id)) == 2


def test_result_cannot_use_another_input_digest(research_case):
    case = research_case
    case.ledger.claim(case.execution_id)
    with pytest.raises(ResearchError, match="frozen execution"):
        case.ledger.publish(
            case.failed_result(input_digest="0" * 64), expected_revision=0
        )
    assert case.ledger.inspect(case.execution_id) is None
    assert len(case.ledger.events(case.execution_id)) == 1


def test_manifest_crash_does_not_publish_a_result_or_final_event(
    research_case, monkeypatch
):
    case = research_case
    case.ledger.claim(case.execution_id)
    original = LocalArtifacts.commit

    def fail_manifest(self, data, **kwargs):
        if kwargs["kind"] == "result_manifest":
            raise OSError(
                "Synthetic failure between artifact commit and pointer commit"
            )
        return original(self, data, **kwargs)

    monkeypatch.setattr(LocalArtifacts, "commit", fail_manifest)
    with pytest.raises(OSError):
        case.ledger.publish(case.failed_result(), expected_revision=0)
    assert case.ledger.inspect(case.execution_id) is None
    assert len(case.ledger.events(case.execution_id)) == 1
    monkeypatch.setattr(LocalArtifacts, "commit", original)
    recovered = case.ledger.publish(case.failed_result(), expected_revision=0)
    assert recovered.execution_status == "failed"
    assert len(case.ledger.events(case.execution_id)) == 2


def test_events_are_idempotent_and_terminal_runs_reject_new_events(research_case):
    case = research_case
    case.ledger.claim(case.execution_id)
    event = EventInput(
        event_id=uuid4(),
        execution_id=case.execution_id,
        occurred_at=datetime.now(UTC),
        phase_code="test_parse",
        payload=PhasePayload(type="phase_changed", completed_units=1, planned_units=2),
    )
    first = case.ledger.append_event(event)
    assert case.ledger.append_event(event) == first
    changed = event.model_copy(update={"phase_code": "different"})
    with pytest.raises(ResearchError, match="cannot change"):
        case.ledger.append_event(changed)
    case.ledger.publish(case.failed_result(), expected_revision=0)
    assert case.ledger.append_event(event) == first
    with pytest.raises(ResearchError, match="cannot append"):
        case.ledger.append_event(event.model_copy(update={"event_id": uuid4()}))


def test_frozen_input_tampering_is_detected_before_claim(research_case):
    case = research_case
    with case.ledger._connect() as db:
        row = case.ledger._row(db, case.execution_id)
        import json

        path = (
            case.artifacts.root
            / str(case.execution_id)
            / json.loads(row["spec_ref"])["path"]
        )
    path.write_bytes(b"modified input")
    with pytest.raises(ResearchError, match="Artifact bytes"):
        case.ledger.claim(case.execution_id)


def test_missing_output_artifact_rolls_back_publication(research_case):
    case = research_case
    ref = case.artifacts.commit(b"diagnostic", kind="log", schema_version="test/1")
    (case.artifacts.root / str(case.execution_id) / ref.path).unlink()
    case.ledger.claim(case.execution_id)
    with pytest.raises(ResearchError, match="unavailable"):
        case.ledger.publish(case.failed_result(artifacts=(ref,)), expected_revision=0)
    assert case.ledger.inspect(case.execution_id) is None
    assert len(case.ledger.events(case.execution_id)) == 1


def test_historical_receipt_digest_does_not_change_when_schema_adds_defaults(
    research_case,
):
    import json

    from semflow_contracts.common import canonical_bytes, digest
    from semflow_contracts.errors import ResearchError
    from semflow_contracts.runs import validate_spec

    case = research_case
    historical = case.spec.model_dump(mode="json")
    historical["policy"].pop("max_no_progress")
    frozen = case.artifacts.commit(
        canonical_bytes(historical),
        kind="run_spec",
        schema_version=case.spec.schema_version,
    )
    with case.ledger._connect() as db:
        db.execute(
            "UPDATE executions SET spec=?, input_digest=?, spec_ref=? WHERE id=?",
            (
                canonical_bytes(historical).decode(),
                digest(historical),
                frozen.model_dump_json(),
                str(case.execution_id),
            ),
        )
    assert case.ledger.claim(case.execution_id)
    result = case.failed_result(input_digest=digest(historical))
    receipt = case.ledger.publish(result, expected_revision=0)
    assert case.ledger.inspect(case.execution_id) == receipt
    with pytest.raises(ResearchError, match="different inputs"):
        case.ledger.create(validate_spec(historical))
    with case.ledger._connect() as db:
        row = case.ledger._row(db, case.execution_id)
        assert json.loads(row["spec"]) == historical
