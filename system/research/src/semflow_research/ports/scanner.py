"""Algorithm extracted from app.ports.scanner.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

from pathlib import Path
from typing import Protocol

from semflow_research.domain.errors import ScanPlan


class Scanner(Protocol):
    def version(self) -> str: ...

    def create_database(
        self, source: Path, output: Path, log: Path, plan: ScanPlan
    ) -> None: ...

    def analyze(
        self, database: Path, output: Path, log: Path, plan: ScanPlan
    ) -> None: ...
