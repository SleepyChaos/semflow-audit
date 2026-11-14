"""Durable shared model budget; unresolved external calls are never replayed.

The owner is the discovery execution, not each child branch. A reservation is
committed before sending to a provider; missing outcomes stay charged and block
new calls after recovery. An explicit new attempt is required for unknown work.
"""

import json
import time
from uuid import UUID

from semflow_contracts.common import canonical_bytes, digest
from semflow_contracts.errors import ResearchError


class CallJournal:
    def __init__(self, ledger, owner_id: UUID, execution_id: UUID):
        self.ledger, self.owner_id, self.execution_id = ledger, owner_id, execution_id
        with ledger._connect() as db:
            db.executescript(
                "CREATE TABLE IF NOT EXISTS model_budgets (owner_id TEXT PRIMARY KEY, "
                "policy_digest TEXT NOT NULL, started_at REAL NOT NULL);"
                "CREATE TABLE IF NOT EXISTS model_calls (call_id TEXT PRIMARY KEY, "
                "owner_id TEXT NOT NULL, execution_id TEXT NOT NULL, input_digest TEXT NOT NULL, "
                "reserved_tokens INTEGER NOT NULL, started_at REAL NOT NULL, "
                "state TEXT NOT NULL, receipt TEXT);"
            )
            owner = ledger._row(db, owner_id)
            member = ledger._row(db, execution_id)
            self.spec = ledger._store(
                owner
            )  # Verify frozen input bytes before using budgets.
            owner_spec = json.loads(owner["spec"])
            member_spec = json.loads(member["spec"])
            ledger._store(member)
            if owner_id != execution_id and (
                member_spec["lineage"]["parent_execution_id"] != str(owner_id)
                or member_spec["source"] != owner_spec["source"]
                or owner_spec["module"] != "discovery"
                or owner_spec["operation"] != "discover"
            ):
                raise ResearchError(
                    "identity_mismatch",
                    "Call budget requires a declared discovery parent and identical source",
                )
            if owner_id != execution_id:
                from semflow_research.runtime.children import require_binding

                require_binding(ledger, db, owner_id, execution_id)
            self.policy = owner_spec["policy"]
            self.method_call_limit = (
                member_spec["inputs"]["method_policy"].get("model_call_limit")
                if member_spec["module"] == "repair"
                and member_spec["operation"] == "generate"
                else None
            )
            self.policy_digest = digest(self.policy)

    def reserve(
        self, call_id: UUID, *, input_digest: str, reserved_tokens: int
    ) -> float:
        if reserved_tokens < 1:
            raise ResearchError(
                "invalid_contract",
                "Model reservation must charge input and output tokens",
            )
        now = time.time()
        with self.ledger._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self.ledger._row(db, self.execution_id)
            if row["status"] != "running":
                raise ResearchError(
                    "execution_conflict",
                    "Model calls require a claimed running execution",
                )
            db.execute(
                "INSERT OR IGNORE INTO model_budgets VALUES(?,?,?)",
                (str(self.owner_id), self.policy_digest, now),
            )
            budget = db.execute(
                "SELECT * FROM model_budgets WHERE owner_id=?", (str(self.owner_id),)
            ).fetchone()
            if budget["policy_digest"] != self.policy_digest:
                raise ResearchError(
                    "integrity_error", "Shared model budget policy changed"
                )
            previous = db.execute(
                "SELECT * FROM model_calls WHERE call_id=?", (str(call_id),)
            ).fetchone()
            if previous:
                raise ResearchError(
                    "execution_conflict",
                    "Model call identity already exists; consume its receipt, never resend",
                )
            rows = db.execute(
                "SELECT * FROM model_calls WHERE owner_id=?", (str(self.owner_id),)
            ).fetchall()
            # A worker may die after the provider accepted a request. Charging
            # reservations alone is insufficient: resending could change science.
            if any(row["state"] in {"reserved", "unknown"} for row in rows):
                raise ResearchError(
                    "external_outcome_unknown",
                    "A previous external call has no verified outcome; create a new attempt",
                )
            tokens = 0
            for row in rows:
                receipt = json.loads(row["receipt"]) if row["receipt"] else {}
                actual = (receipt.get("input_tokens"), receipt.get("output_tokens"))
                tokens += (
                    sum(actual)
                    if all(type(value) is int and value >= 0 for value in actual)
                    else row["reserved_tokens"]
                )
            limits = self.policy
            exceeded = (
                limits["max_calls"] is not None
                and len(rows) + 1 > limits["max_calls"]
                or limits["max_tokens"] is not None
                and tokens + reserved_tokens > limits["max_tokens"]
                or limits["max_seconds"] is not None
                and now - budget["started_at"] >= limits["max_seconds"]
                or self.method_call_limit is not None
                and len(rows) + 1 > self.method_call_limit
            )
            if exceeded:
                raise ResearchError(
                    "budget_exhausted",
                    "Shared execution call/token/time budget exhausted",
                )
            db.execute(
                "INSERT INTO model_calls VALUES(?,?,?,?,?,?,?,NULL)",
                (
                    str(call_id),
                    str(self.owner_id),
                    str(self.execution_id),
                    input_digest,
                    reserved_tokens,
                    now,
                    "reserved",
                ),
            )
            remaining = (
                limits["max_seconds"] - (now - budget["started_at"])
                if limits["max_seconds"]
                else float("inf")
            )
            return min(limits["per_call_timeout_seconds"], remaining)

    def finish(self, call_id: UUID, receipt: dict, *, outcome: str):
        if outcome not in {"known", "unknown"}:
            raise ResearchError(
                "invalid_contract", "Unknown external call outcome state"
            )
        raw = canonical_bytes(receipt).decode()
        with self.ledger._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM model_calls WHERE call_id=?", (str(call_id),)
            ).fetchone()
            if (
                row is None
                or row["owner_id"] != str(self.owner_id)
                or row["execution_id"] != str(self.execution_id)
            ):
                raise ResearchError(
                    "identity_mismatch", "Call receipt belongs to another execution"
                )
            if row["state"] != "reserved":
                if row["state"] == outcome and row["receipt"] == raw:
                    return
                raise ResearchError(
                    "execution_conflict", "External call receipt is immutable"
                )
            db.execute(
                "UPDATE model_calls SET state=?,receipt=? WHERE call_id=?",
                (outcome, raw, str(call_id)),
            )

    def receipts(self):
        with self.ledger._connect() as db:
            rows = db.execute(
                "SELECT * FROM model_calls WHERE owner_id=? ORDER BY started_at,call_id",
                (str(self.owner_id),),
            ).fetchall()
            return tuple(
                {
                    **dict(row),
                    "receipt": json.loads(row["receipt"]) if row["receipt"] else None,
                }
                for row in rows
            )
