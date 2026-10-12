from pathlib import Path
from typing import Protocol

from app.domain.audit import ScanPlan


class Scanner(Protocol):
    def version(self) -> str: ...
    def create_database(
        self, source: Path, output: Path, log: Path, plan: ScanPlan
    ) -> None: ...
    def analyze(
        self, database: Path, output: Path, log: Path, plan: ScanPlan
    ) -> None: ...
