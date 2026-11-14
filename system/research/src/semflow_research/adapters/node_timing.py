"""Algorithm extracted from app.adapters.node_timing.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""One immutable timing record per invocation, including failures and pauses."""
import json
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from langgraph.errors import GraphInterrupt

from semflow_research.domain.errors import AuditCancelled, ExecutionCancelled


def timed_node(directory, name, operation):

    def invoke(state):
        root = directory / "node-timings"
        root.mkdir(parents=True, exist_ok=True)
        identifier = str(uuid4())
        record = {
            "schema_version": 1,
            "invocation_id": identifier,
            "node": name,
            "started_at": datetime.now(UTC).isoformat(),
            "attempt_before": state.get("attempt", 0),
            "status": "running",
        }
        path = root / f"{identifier}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        start = perf_counter()
        try:
            result = operation(state)
            record["status"] = "completed"
            record["attempt_after"] = result.get("attempt", state.get("attempt", 0))
            if "draft_ok" in result:
                record["candidate_passed"] = result["draft_ok"]
            return result
        except GraphInterrupt:
            record["status"] = "interrupted"
            raise
        except (ExecutionCancelled, AuditCancelled):
            record["status"] = "cancelled"
            raise
        except BaseException as exc:
            record["status"] = "failed"
            record["error_type"] = type(exc).__name__
            raise
        finally:
            record["seconds"] = perf_counter() - start
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2))

    return invoke
