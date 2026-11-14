"""Small SQLite record boundary for scientific state, isolated by execution scope.

Only equality/in-list lookups are supported. This is not a platform ORM adapter:
the schema has no User, workspace, AuditRun, StageRun or platform foreign keys.
Each save appends a revision; downstream executions cannot rewrite upstream state.
"""

import hashlib
import sqlite3
import threading
from contextlib import closing, contextmanager
from pathlib import Path
from types import MappingProxyType
from uuid import UUID

from semflow_contracts.common import canonical_bytes
from semflow_contracts.errors import ResearchError

from semflow_research.state import models

KINDS = MappingProxyType(
    {
        model.__name__: model
        for model in (
            models.SourceRecord,
            models.ExecutionRecord,
            models.Evidence,
            models.Candidate,
            models.Decision,
            models.RepairRecord,
            models.RuleVersion,
            models.KnowledgeChunk,
        )
    }
)


class RecordStore:
    def __init__(
        self,
        path: Path,
        execution_id: UUID,
        upstream: tuple[UUID, ...] = (),
        *,
        read_upstream=True,
    ):
        self.path, self.execution_id = path, execution_id
        self.scope = (execution_id, *dict.fromkeys(upstream))
        self.read_upstream = read_upstream
        self._lock = threading.RLock()
        self._connection = None
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS scientific_records ("
                "execution_id TEXT NOT NULL, kind TEXT NOT NULL, entity_id TEXT NOT NULL, "
                "revision INTEGER NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL, "
                "PRIMARY KEY(execution_id, kind, entity_id, revision))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS scientific_inputs ("
                "execution_id TEXT NOT NULL, kind TEXT NOT NULL, entity_id TEXT NOT NULL, "
                "producer TEXT NOT NULL, digest TEXT NOT NULL, "
                "PRIMARY KEY(execution_id, kind, entity_id))"
            )

    @contextmanager
    def transaction(self):
        # The object is scoped to one execution; nesting reuses its transaction.
        # Distinct executions use distinct stores/connections, not global mutable state.
        with self._lock:
            nested = self._connection is not None
            if not nested:
                self._connection = sqlite3.connect(self.path, timeout=30)
                self._connection.row_factory = sqlite3.Row
                self._connection.execute("BEGIN IMMEDIATE")
            try:
                yield self
                if not nested:
                    self._connection.commit()
            except BaseException:
                if not nested:
                    self._connection.rollback()
                raise
            finally:
                if not nested:
                    self._connection.close()
                    self._connection = None

    def _rows(self, kind):
        if kind.__name__ not in KINDS or KINDS[kind.__name__] is not kind:
            raise ResearchError("invalid_contract", "Unknown scientific record kind")
        # Public bundle imports authorize selected immutable records, not every
        # row owned by their producer. Only explicitly requested low-level stores
        # read upstream partitions; kernels consume their local input namespace.
        query_scope = self.scope if self.read_upstream else (self.execution_id,)
        placeholders = ",".join("?" for _ in query_scope)
        rows = self._connection.execute(
            "SELECT * FROM scientific_records r WHERE kind = ? "
            f"AND execution_id IN ({placeholders}) AND revision = ("
            "SELECT MAX(revision) FROM scientific_records v WHERE v.execution_id=r.execution_id "
            "AND v.kind=r.kind AND v.entity_id=r.entity_id)",
            (kind.__name__, *map(str, query_scope)),
        ).fetchall()
        result = {}
        # Prefer the current execution's explicitly imported source context.
        for owner in reversed(query_scope):
            for row in rows:
                if row["execution_id"] != str(owner):
                    continue
                raw = row["payload"].encode()
                if hashlib.sha256(raw).hexdigest() != row["digest"]:
                    raise ResearchError(
                        "integrity_error", "Scientific record revision was modified"
                    )
                result[row["entity_id"]] = kind.model_validate_json(raw)
        return list(result.values())

    def list(self, kind, /, **filters):
        with self.transaction():
            rows = self._rows(kind)
            order = filters.pop("_order", None)
            descending = filters.pop("_descending", False)
            for key, value in filters.items():
                field = key.removesuffix("__in")
                if field not in kind.model_fields and not hasattr(kind, field):
                    raise ResearchError(
                        "invalid_contract", "Unknown scientific record filter"
                    )
                if key.endswith("__in"):
                    values = {str(item) for item in value}
                    rows = [r for r in rows if str(getattr(r, field)) in values]
                else:
                    rows = [
                        r
                        for r in rows
                        if getattr(r, field) == value
                        or str(getattr(r, field)) == str(value)
                    ]
            return (
                sorted(rows, key=lambda row: getattr(row, order), reverse=descending)
                if order
                else rows
            )

    def get(self, kind, identifier):
        rows = self.list(kind, id=UUID(str(identifier)))
        return rows[0] if rows else None

    def first(self, kind, /, **filters):
        rows = self.list(kind, **filters)
        return rows[0] if rows else None

    def one(self, kind, /, **filters):
        rows = self.list(kind, **filters)
        if len(rows) != 1:
            raise ResearchError(
                "identity_mismatch", "Expected one scoped scientific record"
            )
        return rows[0]

    def optional_one(self, kind, /, **filters):
        rows = self.list(kind, **filters)
        if len(rows) > 1:
            raise ResearchError(
                "identity_mismatch", "Scientific record identity is not unique"
            )
        return rows[0] if rows else None

    def import_record(self, record, producer: UUID):
        """Import an already validated input once; never authorize its mutation."""
        if producer not in self.scope:
            raise ResearchError(
                "identity_mismatch", "Imported record is not an authorized upstream"
            )
        kind = type(record)
        if KINDS.get(kind.__name__) is not kind:
            raise ResearchError("invalid_contract", "Unknown scientific record kind")
        identity = (
            record.id
            if kind is models.ExecutionRecord
            else getattr(record, "execution_id", producer)
        )
        if identity != producer:
            raise ResearchError(
                "identity_mismatch",
                "Imported record producer does not match its identity",
            )
        raw = canonical_bytes(record)
        checksum = hashlib.sha256(raw).hexdigest()
        with self.transaction():
            frozen = self._connection.execute(
                "SELECT producer, digest FROM scientific_inputs WHERE execution_id=? AND kind=? AND entity_id=?",
                (str(self.execution_id), kind.__name__, str(record.id)),
            ).fetchone()
            if frozen and (
                frozen["producer"] != str(producer) or frozen["digest"] != checksum
            ):
                raise ResearchError("integrity_error", "Frozen imported record changed")
            old = self._connection.execute(
                "SELECT digest FROM scientific_records WHERE execution_id=? AND kind=? AND entity_id=?",
                (str(self.execution_id), type(record).__name__, str(record.id)),
            ).fetchall()
            if old:
                if any(row["digest"] != checksum for row in old):
                    raise ResearchError(
                        "integrity_error", "Frozen imported record changed"
                    )
                return
            self._connection.execute(
                "INSERT INTO scientific_inputs VALUES(?,?,?,?,?)",
                (
                    str(self.execution_id),
                    kind.__name__,
                    str(record.id),
                    str(producer),
                    checksum,
                ),
            )
            self._connection.execute(
                "INSERT INTO scientific_records VALUES(?,?,?,?,?,?)",
                (
                    str(self.execution_id),
                    type(record).__name__,
                    str(record.id),
                    1,
                    raw.decode(),
                    checksum,
                ),
            )

    def save(self, record):
        kind = type(record)
        if KINDS.get(kind.__name__) is not kind:
            raise ResearchError("invalid_contract", "Unknown scientific record kind")
        producer = getattr(record, "execution_id", self.execution_id)
        if kind is models.ExecutionRecord:
            producer = record.id
        if producer != self.execution_id:
            raise ResearchError(
                "identity_mismatch", "Cannot modify an upstream scientific execution"
            )
        raw = canonical_bytes(record)
        value = hashlib.sha256(raw).hexdigest()
        with self.transaction():
            frozen = self._connection.execute(
                "SELECT 1 FROM scientific_inputs WHERE execution_id=? AND kind=? AND entity_id=?",
                (str(self.execution_id), kind.__name__, str(record.id)),
            ).fetchone()
            if frozen:
                raise ResearchError(
                    "identity_mismatch",
                    "Cannot modify a frozen imported scientific record",
                )
            previous = self._connection.execute(
                "SELECT revision, digest FROM scientific_records WHERE execution_id=? AND kind=? "
                "AND entity_id=? ORDER BY revision DESC LIMIT 1",
                (str(self.execution_id), kind.__name__, str(record.id)),
            ).fetchone()
            if previous and previous["digest"] == value:
                return
            revision = previous["revision"] + 1 if previous else 1
            self._connection.execute(
                "INSERT INTO scientific_records VALUES(?,?,?,?,?,?)",
                (
                    str(self.execution_id),
                    kind.__name__,
                    str(record.id),
                    revision,
                    raw.decode(),
                    value,
                ),
            )

    def commit(self):
        # Commit belongs to transaction(), including nested source evidence writes.
        # Call sites retain this named boundary without opening an implicit global session.
        return None
