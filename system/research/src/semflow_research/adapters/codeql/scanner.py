"""Algorithm extracted from app.adapters.codeql.scanner.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

import json
import platform
import shutil
import subprocess
from pathlib import Path

from semflow_research.adapters.codeql.process import run_command
from semflow_research.domain.errors import AuditError, ScanPlan


class CodeQLScanner:
    def __init__(self, *, _kernel):
        self._kernel = _kernel

    def version(self) -> str:
        _kernel = self._kernel
        try:
            result = subprocess.run(
                [_kernel.settings.CODEQL_BIN, "version", "--format=json"],
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
        _kernel = self._kernel
        runtime = None
        extractor_options = []
        if plan.language == "python":
            interpreter = shutil.which(_kernel.settings.CODEQL_PYTHON_BIN)
            if interpreter is None:
                raise AuditError("找不到配置的 Python 抽取解释器")
            if platform.system() == "Windows":
                runtime = Path(interpreter).resolve().parent
                extractor_options.append(
                    "--extractor-option=python_executable_name=python"
                )
            else:
                runtime = (log.parent / "runtime").resolve()
                runtime.mkdir(exist_ok=True)
                alias = runtime / "python3"
                if not alias.exists():
                    alias.symlink_to(interpreter)
        run_command(
            [
                _kernel.settings.CODEQL_BIN,
                "database",
                "create",
                str(output),
                f"--language={plan.language}",
                f"--source-root={source}",
                f"--threads={_kernel.settings.CODEQL_THREADS}",
                "--build-mode=none",
                *extractor_options,
            ],
            log,
            _kernel.settings.SCAN_TIMEOUT,
            runtime_path=runtime,
        )

    def analyze(self, database: Path, output: Path, log: Path, plan: ScanPlan) -> None:
        _kernel = self._kernel
        name, version = plan.query_pack.split("@", 1)
        pack = _kernel.settings.CODEQL_PACK_PATH / name / version
        query = pack / plan.suite
        if not query.is_file():
            raise AuditError("固定版本查询包未安装")
        run_command(
            [
                _kernel.settings.CODEQL_BIN,
                "database",
                "analyze",
                str(database),
                str(query),
                f"--search-path={pack}",
                "--format=sarif-latest",
                f"--output={output}",
                f"--threads={_kernel.settings.CODEQL_THREADS}",
                f"--ram={_kernel.settings.CODEQL_RAM}",
            ],
            log,
            _kernel.settings.SCAN_TIMEOUT,
        )
        if not output.is_file():
            raise AuditError("CodeQL 未生成 SARIF，不能作为成功的零漏洞结果")
