import json
import platform
import sys
from pathlib import Path

from app.adapters.codeql import scanner
from app.adapters.codeql.process import run_command
from app.core.audit_config import audit_settings
from app.domain.audit import ScanPlan


def test_windows_python_extractor_uses_interpreter_directory_without_symlink(
    monkeypatch, tmp_path
):
    interpreter = tmp_path / "Python311" / "python.exe"
    interpreter.parent.mkdir()
    interpreter.touch()
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(scanner.shutil, "which", lambda _: str(interpreter))
    commands = []
    monkeypatch.setattr(
        scanner,
        "run_command",
        lambda args, log, timeout, runtime_path=None: commands.append(
            (args, runtime_path)
        ),
    )

    def forbidden_symlink(*args, **kwargs):
        raise PermissionError(1314, "symbolic link privilege unavailable")

    monkeypatch.setattr(Path, "symlink_to", forbidden_symlink)
    scanner.CodeQLScanner().create_database(
        tmp_path,
        tmp_path / "db",
        tmp_path / "scan.log",
        ScanPlan(
            "python",
            audit_settings.PYTHON_QUERY_PACK,
            "codeql-suites/python-code-scanning.qls",
        ),
    )
    args, runtime = commands[0]
    assert runtime == interpreter.parent
    assert "--extractor-option=python_executable_name=python" in args


def test_tool_environment_keeps_windows_temp_but_excludes_service_credentials(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("TEMP", str(tmp_path))
    monkeypatch.setenv("TMP", str(tmp_path))
    monkeypatch.setenv("AI_API_KEY", "test-secret-must-not-reach-extractor")
    monkeypatch.setenv("DATABASE_URL", "test-database-secret")
    log = tmp_path / "environment.log"
    code = 'import os,json; print(json.dumps({k:os.environ.get(k) for k in ["TEMP","TMP","AI_API_KEY","DATABASE_URL"]}))'
    run_command([sys.executable, "-c", code], log, 10)
    result = json.loads(log.read_text().splitlines()[-1])
    assert result["TEMP"] == str(tmp_path)
    assert result["TMP"] == str(tmp_path)
    assert result["AI_API_KEY"] is None
    assert result["DATABASE_URL"] is None
