"""Scientific state must preserve producer ownership and atomic evidence writes."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from semflow_contracts.errors import ResearchError
from semflow_research.state.models import Candidate, Decision, Evidence, ExecutionRecord
from semflow_research.state.records import RecordStore


def execution(identifier, snapshot):
    return ExecutionRecord(
        id=identifier, snapshot_id=snapshot, kind="scout", method_version="8"
    )


def test_parallel_executions_cannot_observe_or_overwrite_each_other(tmp_path):
    path, snapshot = tmp_path / "records.sqlite3", uuid4()
    identifiers = (uuid4(), uuid4())
    stores = [RecordStore(path, identifier) for identifier in identifiers]
    with ThreadPoolExecutor(2) as pool:
        list(
            pool.map(
                lambda pair: pair[0].save(execution(pair[1], snapshot)),
                zip(stores, identifiers),
            )
        )
    for store, own, other in zip(stores, identifiers, reversed(identifiers)):
        assert store.get(ExecutionRecord, own).snapshot_id == snapshot
        assert store.get(ExecutionRecord, other) is None
        with pytest.raises(ResearchError, match="upstream"):
            store.save(execution(other, snapshot))


def test_nested_evidence_and_candidate_save_rollback_together(tmp_path):
    identifier, snapshot = uuid4(), uuid4()
    store = RecordStore(tmp_path / "records.sqlite3", identifier)
    evidence = Evidence(
        execution_id=identifier,
        snapshot_id=snapshot,
        kind="code",
        snapshot_hash="0" * 64,
        reference={"file": "app.py"},
        content="actual",
        digest="a" * 64,
    )
    candidate = Candidate(
        execution_id=identifier,
        snapshot_id=snapshot,
        origin="ai",
        title="Hypothesis",
        description="Needs investigation",
        evidence_ids=[str(evidence.id)],
    )
    with pytest.raises(RuntimeError), store.transaction():
        store.save(evidence)
        with store.transaction():
            store.save(candidate)
            store.commit()  # Must not commit the outer transaction early.
        raise RuntimeError("crash before candidate publication")
    assert store.list(Evidence) == store.list(Candidate) == []
    with store.transaction():
        store.save(evidence)
        store.save(candidate)
    restored = RecordStore(store.path, identifier)
    assert restored.get(Candidate, candidate.id).evidence_ids == [str(evidence.id)]
    assert restored.get(Evidence, evidence.id).content == "actual"


def test_revisions_are_append_only_and_noop_save_is_idempotent(tmp_path):
    identifier, snapshot = uuid4(), uuid4()
    store = RecordStore(tmp_path / "records.sqlite3", identifier)
    value = execution(identifier, snapshot)
    store.save(value)
    store.save(value)
    value.phase = "reading_source"
    store.save(value)
    with store.transaction():
        rows = store._connection.execute(
            "SELECT revision,payload FROM scientific_records ORDER BY revision"
        ).fetchall()
    assert [row["revision"] for row in rows] == [1, 2]
    assert '"phase":"queued"' in rows[0]["payload"]
    assert store.get(ExecutionRecord, identifier).phase == "reading_source"


def test_frozen_imports_cannot_be_changed_even_without_execution_field(tmp_path):
    producer, consumer, snapshot = uuid4(), uuid4(), uuid4()
    store = RecordStore(tmp_path / "records.sqlite3", consumer, (producer,))
    decision = Decision(
        candidate_id=uuid4(),
        actor_id="researcher",
        actor_kind="human",
        status="confirmed",
        reason="Source has been inspected",
        evidence_ids=[str(uuid4())],
    )
    store.import_record(decision, producer)
    store.import_record(decision, producer)
    changed = decision.model_copy(update={"status": "excluded"})
    with pytest.raises(ResearchError, match="frozen imported"):
        store.save(changed)
    with pytest.raises(ResearchError, match="Frozen imported"):
        store.import_record(changed, producer)
    assert store.get(Decision, decision.id).status == "confirmed"
    foreign = execution(uuid4(), snapshot)
    with pytest.raises(ResearchError, match="producer"):
        store.import_record(foreign, producer)


def test_record_tampering_is_not_accepted_as_upstream_input(tmp_path):
    producer, consumer, snapshot = uuid4(), uuid4(), uuid4()
    path = tmp_path / "records.sqlite3"
    upstream = RecordStore(path, producer)
    upstream.save(execution(producer, snapshot))
    downstream = RecordStore(path, consumer, (producer,))
    with upstream.transaction():
        upstream._connection.execute(
            "UPDATE scientific_records SET payload=replace(payload,'queued','failed')"
        )
    with pytest.raises(ResearchError, match="modified"):
        downstream.get(ExecutionRecord, producer)
