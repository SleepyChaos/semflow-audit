"""Read an exact published technical comparison for caller presentation only."""

import json

from semflow_contracts.errors import ResearchError

from semflow_research.runtime.ledger import LocalLedger


def read(envelope, *, root):
    ledger = LocalLedger(root)
    saved = ledger.inspect(envelope.execution_id)
    if saved != envelope:
        raise ResearchError(
            "integrity_error", "Only a published comparison can be projected"
        )
    with ledger._connect() as db:
        store = ledger._store(ledger._row(db, envelope.execution_id))
    return json.loads(store.read(envelope.result.receipt.raw_output))
