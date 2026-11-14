"""Algorithm extracted from app.workflows.state.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

from typing import TypedDict


class ScanState(TypedDict):
    run_id: str
    database_ready: bool
    sarif_ready: bool
    findings_saved: bool
