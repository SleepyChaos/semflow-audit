from typing import TypedDict


class ScanState(TypedDict):
    run_id: str
    database_ready: bool
    sarif_ready: bool
    findings_saved: bool
