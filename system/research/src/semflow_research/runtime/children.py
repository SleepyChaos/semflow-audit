"""Bind planned discovery children before allowing shared budgets or outputs."""

import json
from uuid import uuid5

from semflow_contracts.common import ArtifactRef, digest
from semflow_contracts.errors import ResearchError
from semflow_contracts.runs import validate_spec


def child_id(parent_id, role):
    if role not in {"scan", "scout", "review"}:
        raise ResearchError("invalid_contract", "Unknown discovery child role")
    return uuid5(parent_id, "semflow.discovery." + role + "/1")


def bind_child(ledger, parent, child, role):
    # WIRE-SEND:research.run — peer: factory.assemble / public.discovery.execute.
    # AGENT: bind exact child bytes before execution; child identity, role and
    # lineage must match the receiver and parent budget/output authorization.
    parent, child = validate_spec(parent), validate_spec(child)
    if (
        parent.module != "discovery"
        or parent.operation != "discover"
        or child.module != "discovery"
        or child.operation != role
    ):
        raise ResearchError(
            "identity_mismatch", "Child operation does not match discovery plan"
        )
    if (
        child.execution_id != child_id(parent.execution_id, role)
        or child.lineage.parent_execution_id != parent.execution_id
        or child.source != parent.source
    ):
        raise ResearchError(
            "identity_mismatch",
            "Child identity or source differs from the planned parent",
        )
    expected_version = (
        parent.inputs.scout_method_version
        if role == "scout"
        else parent.inputs.review_method_version
        if role == "review"
        else "1"
    )
    if (
        child.policy != parent.policy
        # Static scanning has no model resource dependency. Model endpoint
        # failure belongs to the scout branch and cannot prevent CodeQL running.
        or child.model != (None if role == "scan" else parent.model)
        or child.prompts != (() if role == "scan" else parent.prompts)
        or child.implementation.code_digest != parent.implementation.code_digest
        or child.implementation.dependency_lock_digest
        != parent.implementation.dependency_lock_digest
        or child.implementation.method_version != expected_version
    ):
        raise ResearchError(
            "identity_mismatch",
            "Child resources, method, prompts or policy differ from the frozen parent",
        )
    planned = getattr(parent.inputs, role)
    if (
        planned is None
        or (role != "review" and child.inputs != planned)
        or (role == "review" and child.inputs.policy != planned)
    ):
        raise ResearchError(
            "identity_mismatch", "Child inputs differ from the enabled parent branch"
        )
    ledger.create(child)
    with ledger._connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = ledger._row(db, parent.execution_id)
        if row["input_digest"] != digest(parent) or row["status"] != "running":
            raise ResearchError(
                "execution_conflict", "Child binding requires its exact running parent"
            )
        previous = db.execute(
            "SELECT * FROM execution_children WHERE parent_id=? AND role=?",
            (str(parent.execution_id), role),
        ).fetchone()
        if previous:
            if previous["child_id"] != str(child.execution_id) or previous[
                "input_digest"
            ] != digest(child):
                raise ResearchError(
                    "execution_conflict", "Discovery child binding is immutable"
                )
            return
        db.execute(
            "INSERT INTO execution_children VALUES(?,?,?,?)",
            (str(parent.execution_id), role, str(child.execution_id), digest(child)),
        )


def require_binding(ledger, db, parent_id, execution_id):
    binding = db.execute(
        "SELECT * FROM execution_children WHERE parent_id=? AND child_id=?",
        (str(parent_id), str(execution_id)),
    ).fetchone()
    row = ledger._row(db, execution_id)
    if binding is None or row["input_digest"] != binding["input_digest"]:
        raise ResearchError(
            "identity_mismatch", "Shared budget requires an exact planned child binding"
        )
    return binding


def published_child_refs(ledger, db, parent_row):
    """Only completed, manifest-verified bound children grant output references."""
    bindings = db.execute(
        "SELECT * FROM execution_children WHERE parent_id=? ORDER BY role",
        (parent_row["id"],),
    ).fetchall()
    refs = []
    for binding in bindings:
        row = ledger._row(db, binding["child_id"])
        spec = validate_spec(json.loads(row["spec"]))
        if (
            row["input_digest"] != binding["input_digest"]
            or digest(spec) != binding["input_digest"]
            or spec.execution_id
            != child_id(spec.lineage.parent_execution_id, binding["role"])
        ):
            raise ResearchError(
                "integrity_error", "Discovery child binding or input bytes changed"
            )
        if row["manifest_ref"] is None:
            continue
        result = ledger.inspect(spec.execution_id)
        # The child cannot change after a terminal receipt. A running partial
        # revision is not adopted as a completed branch result.
        if result.execution_status not in {
            "completed",
            "failed",
            "cancelled",
            "interrupted",
        }:
            continue
        from semflow_research.runtime.ledger import input_artifacts

        refs.extend(input_artifacts(result))
        refs.append(ArtifactRef.model_validate_json(row["manifest_ref"]))
    return tuple(refs)
