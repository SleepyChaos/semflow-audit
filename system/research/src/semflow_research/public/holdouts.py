"""Handles for the existing independent micro-fixtures; never generation inputs."""

from semflow_contracts.errors import ResearchError
from semflow_contracts.rules import HoldoutHandle


def catalog():
    from semflow_research.rules.rule_holdouts import catalog as original_catalog

    return original_catalog()


def select(identifier: str) -> HoldoutHandle:
    metadata = next((row for row in catalog() if row["id"] == identifier), None)
    if metadata is None:
        raise ResearchError("invalid_contract", "Independent dataset is not registered")
    return HoldoutHandle(
        dataset_id=identifier,
        version="1",
        digest=metadata["hash"],
        evaluator_profile="builtin-micro-fixtures/1",
    )
