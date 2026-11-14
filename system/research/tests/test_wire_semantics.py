"""Prevent dangling semantic comments and undeclared cross-boundary JSON changes."""

import io
import re
import tokenize
from collections import defaultdict
from pathlib import Path

import pytest
from semflow_contracts.actions import ApprovalDecision, ControlCommand
from semflow_contracts.bundles import CandidateBundle
from semflow_contracts.checkpoints import CheckpointBundle
from semflow_contracts.common import SourceManifest
from semflow_contracts.events import ExecutionEvent
from semflow_contracts.evidence import EvidenceRecord
from semflow_contracts.openhands import OpenHandsReceipt
from semflow_contracts.repair import OpenHandsPolicy
from semflow_contracts.results import ResultEnvelope, ResultManifest
from semflow_contracts.runs import ScanSpec
from semflow_contracts.wire import MEANINGS

SYSTEM = Path(__file__).resolve().parents[2]


def test_every_declared_json_interface_has_actual_sender_and_receiver_comments():
    markers = defaultdict(lambda: defaultdict(list))
    for package in ("contracts", "research", "research_cli"):
        for path in (SYSTEM / package / "src").rglob("*.py"):
            for token in tokenize.generate_tokens(
                io.StringIO(path.read_text()).readline
            ):
                if token.type != tokenize.COMMENT:
                    continue
                match = re.search(r"WIRE-(SEND|RECV):(research\.[a-z_]+)", token.string)
                if match:
                    direction, identifier = match.groups()
                    markers[identifier][direction].append((str(path), token.start[0]))
    expected = {value.contract_id for value in MEANINGS.values()}
    assert set(markers) == expected
    assert {
        identifier: sorted(directions) for identifier, directions in markers.items()
    } == {identifier: ["RECV", "SEND"] for identifier in expected}


@pytest.mark.parametrize(
    ("name", "schema"),
    [
        ("run", ScanSpec),
        ("result", ResultEnvelope),
        ("manifest", ResultManifest),
        ("evidence", EvidenceRecord),
        ("event", ExecutionEvent),
        ("approval", ApprovalDecision),
        ("control", ControlCommand),
        ("checkpoint", CheckpointBundle),
        ("source", SourceManifest),
        ("bundle", CandidateBundle),
        ("openhands", OpenHandsPolicy),
        ("openhands_receipt", OpenHandsReceipt),
    ],
)
def test_json_schema_exposes_versioned_meaning_and_paired_agent_constraint(
    name, schema
):
    declaration = schema.model_json_schema()
    meaning = MEANINGS[name]
    assert declaration["x-semflow-contract"] == meaning.contract_id
    assert declaration["x-semflow-semantics-revision"] == meaning.semantics_revision
    assert (
        "AGENT:" in declaration["$comment"]
        and "WIRE-SEND" in declaration["$comment"]
        and "WIRE-RECV" in declaration["$comment"]
    )
