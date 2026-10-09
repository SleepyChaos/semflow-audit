import json
from uuid import UUID

from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.sarif import parse_sarif
from app.adapters.snapshot import snapshot_digest
from app.domain.audit import AuditError, ScanPlan
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
        if (
            snapshot_digest(self.artifacts.source(str(run.source_run_id)))
            != run.snapshot_hash
        ):
            raise AuditError("扫描前源码快照完整性检查失败")
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

        run = self.repository.get(run_id)
        if run.custom_rule_ids:
            from app.adapters.codeql.custom import prepare_query, run_query
            from app.services.rules_execution import owned_published_rule

            baseline = directory / "baseline.sarif"
            (directory / "results.sarif").replace(baseline)
            document = json.loads(baseline.read_text())
            for rule_id in run.custom_rule_ids:
                self.repository.update(run_id, phase="supplement")
                rule = owned_published_rule(
                    UUID(rule_id), run.owner_id, run.language, allow_retired=True
                )
                pack = directory / "supplements" / rule_id / "pack"
                prepare_query(
                    pack, run.language, rule.query, rule.modules, rule.dependencies
                )
                sarif = pack.parent / "results.sarif"
                run_query(
                    directory / "database",
                    pack,
                    sarif,
                    directory / "execution.log",
                    run.snapshot_hash,
                )
                extra = json.loads(sarif.read_text())
                for result in extra["runs"]:
                    result.setdefault("properties", {})["audit_rule_version"] = rule_id
                document["runs"].extend(extra["runs"])
            (directory / "results.sarif").write_text(json.dumps(document))

    def save_findings(self, run_id: str, finalize: bool = True) -> None:
        run = self.repository.get(run_id)
        self.repository.update(run_id, phase="parse")
        findings = parse_sarif(
            self.artifacts.directory(run_id) / "results.sarif", run.snapshot_hash
        )
        changes = {"findings": findings, "phase": "codeql_ready"}
        if finalize:
            changes.update(phase="completed", status="completed")
        self.repository.update(run_id, **changes)
