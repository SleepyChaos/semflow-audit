from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.sarif import parse_sarif
from app.domain.audit import ScanPlan
from app.persistence.audit_repository import AuditRepository
from app.ports.scanner import Scanner


class ScanService:
    def __init__(
        self, repository: AuditRepository, artifacts: ArtifactStore, scanner: Scanner
    ):
        self.repository, self.artifacts, self.scanner = repository, artifacts, scanner

    def plan(self, run_id: str) -> ScanPlan:
        run = self.repository.get(run_id)
        return ScanPlan(run.language, run.query_pack, run.suite)

    def create_database(self, run_id: str) -> None:
        run = self.repository.get(run_id)
        directory = self.artifacts.directory(run_id)
        self.repository.update(
            run_id, phase="database", codeql_version=self.scanner.version()
        )
        self.scanner.create_database(
            self.artifacts.source(str(run.source_run_id)),
            directory / "database",
            directory / "execution.log",
            self.plan(run_id),
        )

    def scan(self, run_id: str) -> None:
        directory = self.artifacts.directory(run_id)
        self.repository.update(run_id, phase="scan")
        self.scanner.analyze(
            directory / "database",
            directory / "results.sarif",
            directory / "execution.log",
            self.plan(run_id),
        )

    def save_findings(self, run_id: str) -> None:
        run = self.repository.get(run_id)
        self.repository.update(run_id, phase="parse")
        findings = parse_sarif(
            self.artifacts.directory(run_id) / "results.sarif", run.snapshot_hash
        )
        self.repository.update(
            run_id, findings=findings, phase="completed", status="completed"
        )
