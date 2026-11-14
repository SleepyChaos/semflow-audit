from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from semflow_contracts.errors import ResearchError
from semflow_contracts.runs import validate_spec
from semflow_research.runtime.calls import CallJournal
from semflow_research.runtime.children import bind_child, child_id


def test_budget_reservation_is_durable_before_external_call(research_case):
    case = research_case
    case.ledger.claim(case.execution_id)
    journal = CallJournal(case.ledger, case.execution_id, case.execution_id)
    call_id = uuid4()
    journal.reserve(call_id, input_digest="a" * 64, reserved_tokens=400)
    restored = CallJournal(case.ledger, case.execution_id, case.execution_id)
    assert restored.receipts()[0]["state"] == "reserved"
    with pytest.raises(ResearchError, match="no verified outcome"):
        restored.reserve(uuid4(), input_digest="b" * 64, reserved_tokens=400)
    restored.finish(
        call_id, {"input_tokens": 100, "output_tokens": 200}, outcome="known"
    )
    restored.reserve(uuid4(), input_digest="b" * 64, reserved_tokens=400)


def test_concurrent_reservations_cannot_exceed_budget(research_case):
    case = research_case
    case.ledger.claim(case.execution_id)

    def reserve(_):
        journal = CallJournal(case.ledger, case.execution_id, case.execution_id)
        try:
            journal.reserve(uuid4(), input_digest="a" * 64, reserved_tokens=400)
            return "reserved"
        except ResearchError as exc:
            return exc.code

    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(reserve, range(2)))
    assert sorted(outcomes) == ["external_outcome_unknown", "reserved"]


def test_outcomes_are_immutable_and_unknown_calls_stay_charged(research_case):
    case = research_case
    case.ledger.claim(case.execution_id)
    journal = CallJournal(case.ledger, case.execution_id, case.execution_id)
    identifier = uuid4()
    journal.reserve(identifier, input_digest="a" * 64, reserved_tokens=400)
    receipt = {"input_tokens": None, "output_tokens": None, "error_code": "timeout"}
    journal.finish(identifier, receipt, outcome="unknown")
    journal.finish(identifier, receipt, outcome="unknown")
    with pytest.raises(ResearchError, match="immutable"):
        journal.finish(
            identifier, {"input_tokens": 1, "output_tokens": 1}, outcome="known"
        )
    with pytest.raises(ResearchError, match="no verified outcome"):
        journal.reserve(uuid4(), input_digest="a" * 64, reserved_tokens=400)


def test_child_budgets_charge_parent_instead_of_resetting(research_case):
    case = research_case
    value = case.spec.model_dump(mode="json")
    value.update(
        operation="discover",
        inputs={"scan": value["inputs"], "required_branches": ["scan"]},
    )
    value["execution_id"] = str(uuid4())
    value["policy"]["max_calls"] = 1
    parent = validate_spec(value)
    case.ledger.create(parent)
    case.ledger.claim(parent.execution_id)
    first = CallJournal(case.ledger, parent.execution_id, parent.execution_id)
    identifier = uuid4()
    first.reserve(identifier, input_digest="a" * 64, reserved_tokens=400)
    first.finish(
        identifier, {"input_tokens": 100, "output_tokens": 100}, outcome="known"
    )
    child_value = case.spec.model_dump(mode="json")
    child_value["execution_id"] = str(child_id(parent.execution_id, "scan"))
    child_value["lineage"]["parent_execution_id"] = str(parent.execution_id)
    child_value["policy"] = parent.policy.model_dump(mode="json")
    child_value["implementation"]["method_version"] = "1"
    child = validate_spec(child_value)
    bind_child(case.ledger, parent, child, "scan")
    case.ledger.claim(child.execution_id)
    second = CallJournal(case.ledger, parent.execution_id, child.execution_id)
    with pytest.raises(ResearchError, match="Shared execution"):
        second.reserve(uuid4(), input_digest="b" * 64, reserved_tokens=400)
    assert second.receipts()[0]["execution_id"] == str(parent.execution_id)


def test_declaring_parent_id_does_not_grant_its_budget(research_case):
    case = research_case
    value = case.spec.model_dump(mode="json")
    value.update(
        execution_id=str(uuid4()),
        operation="discover",
        inputs={"scan": value["inputs"], "required_branches": ["scan"]},
    )
    parent = validate_spec(value)
    case.ledger.create(parent)
    case.ledger.claim(parent.execution_id)
    value = case.spec.model_dump(mode="json")
    value["execution_id"] = str(child_id(parent.execution_id, "scan"))
    value["lineage"]["parent_execution_id"] = str(parent.execution_id)
    child = validate_spec(value)
    case.ledger.create(child)
    with pytest.raises(ResearchError, match="planned child binding"):
        CallJournal(case.ledger, parent.execution_id, child.execution_id)
