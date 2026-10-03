import json
import shutil
import subprocess
from pathlib import Path

from app.adapters.codeql.process import run_command
from app.core.audit_config import audit_settings
from app.domain.audit import AuditError, ScanPlan


class CodeQLScanner:
    def version(self) -> str:
        try:
            result = subprocess.run(
                [audit_settings.CODEQL_BIN, "version", "--format=json"],
                capture_output=True,
                text=True,
                timeout=15,
                check=True,
            )
            return json.loads(result.stdout)["version"]
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            raise AuditError("CodeQL CLI 不可用") from exc

    def create_database(
        self, source: Path, output: Path, log: Path, plan: ScanPlan
    ) -> None:
        runtime = None
        if plan.language == "python":
            interpreter = shutil.which(audit_settings.CODEQL_PYTHON_BIN)
            if interpreter is None:
                raise AuditError("找不到配置的 Python 抽取解释器")
            runtime = (log.parent / "runtime").resolve()
            runtime.mkdir(exist_ok=True)
            alias = runtime / "python3"
            if not alias.exists():
                alias.symlink_to(interpreter)
        run_command(
            [
                audit_settings.CODEQL_BIN,
                "database",
                "create",
                str(output),
                f"--language={plan.language}",
                f"--source-root={source}",
                f"--threads={audit_settings.CODEQL_THREADS}",
                "--build-mode=none",
            ],
            log,
            audit_settings.SCAN_TIMEOUT,
            runtime_path=runtime,
        )

    def analyze(self, database: Path, output: Path, log: Path, plan: ScanPlan) -> None:
        name, version = plan.query_pack.split("@", 1)
        pack = audit_settings.CODEQL_PACK_PATH / name / version
        query = pack / plan.suite
        if not query.is_file():
            raise AuditError("固定版本查询包未安装")
        run_command(
            [
                audit_settings.CODEQL_BIN,
                "database",
                "analyze",
                str(database),
                str(query),
                f"--search-path={pack}",
                "--format=sarif-latest",
                f"--output={output}",
                f"--threads={audit_settings.CODEQL_THREADS}",
                f"--ram={audit_settings.CODEQL_RAM}",
            ],
            log,
            audit_settings.SCAN_TIMEOUT,
        )
        if not output.is_file():
            raise AuditError("CodeQL 未生成 SARIF，不能作为成功的零漏洞结果")
