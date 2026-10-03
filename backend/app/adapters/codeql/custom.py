"""Fixed-dependency custom query compilation and real positive/negative execution."""

import hashlib
import json
import os
import re
from pathlib import Path

import yaml

from app.adapters.codeql.process import run_command
from app.adapters.codeql.sarif import parse_sarif
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.snapshot import snapshot_digest
from app.adapters.syntax import check_syntax
from app.core.audit_config import audit_settings
from app.domain.audit import AuditError, ScanPlan


def query_digest(query: str, modules: dict) -> str:
    return hashlib.sha256(
        json.dumps({"query": query, "modules": modules}, sort_keys=True).encode()
    ).hexdigest()


def fixed_dependencies(language: str) -> dict:
    spec = (
        audit_settings.PYTHON_QUERY_PACK
        if language == "python"
        else audit_settings.JAVASCRIPT_QUERY_PACK
    )
    name, version = spec.split("@")
    lock = audit_settings.CODEQL_PACK_PATH / name / version / "codeql-pack.lock.yml"
    if not lock.exists():
        raise AuditError("固定查询包依赖清单不存在")
    return yaml.safe_load(lock.read_text())["dependencies"]


def search_paths(pack: Path) -> str:
    dependencies = yaml.safe_load((pack / "codeql-pack.lock.yml").read_text())[
        "dependencies"
    ]
    paths = [str(pack)]
    for name, metadata in dependencies.items():
        path = audit_settings.CODEQL_PACK_PATH / name / metadata["version"]
        if not (path / "qlpack.yml").is_file():
            raise AuditError(
                "固定版本库源码未安装，请运行 scripts/install_query_sources.py"
            )
        paths.append(str(path))
    return os.pathsep.join(paths)


def prepare_query(
    pack: Path, language: str, query: str, modules: dict, dependencies: dict
) -> Path:
    for field in ["id", "name", "description", "kind", "problem.severity", "precision"]:
        if not re.search(r"@" + re.escape(field) + r"\s+\S+", query):
            raise AuditError(f"生成查询缺少 @{field} 元数据")
    if not re.search(r"@id\s+(?:custom|audit)/[a-z0-9/-]+", query):
        raise AuditError("生成规则必须使用 custom/ 或 audit/ 命名空间")
    pack.mkdir(parents=True, exist_ok=True)
    library = "codeql/python-all" if language == "python" else "codeql/javascript-all"
    if library not in dependencies:
        raise AuditError("规则依赖未固定语言库版本")
    (pack / "qlpack.yml").write_text(
        yaml.safe_dump(
            {
                "name": "audit/generated",
                "version": "0.0.1",
                "library": False,
                "dependencies": {library: dependencies[library]["version"]},
            }
        )
    )
    (pack / "codeql-pack.lock.yml").write_text(
        yaml.safe_dump({"lockVersion": "1.0.0", "dependencies": dependencies})
    )
    for name, content in modules.items():
        if (
            not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*\.qll", name)
            or len(content) > 50000
        ):
            raise AuditError("规则模型模块必须是当前包内的有限 .qll 文件")
        (pack / name).write_text(content)
    path = pack / "generated.ql"
    path.write_text(query)
    return path


def compile_query(pack: Path, log: Path) -> None:
    run_command(
        [
            audit_settings.CODEQL_BIN,
            "query",
            "compile",
            "--check-only",
            f"--additional-packs={search_paths(pack)}",
            f"--ram={audit_settings.CODEQL_RAM}",
            str(pack / "generated.ql"),
        ],
        log,
        audit_settings.SCAN_TIMEOUT,
    )


def run_query(
    database: Path, pack: Path, output: Path, log: Path, snapshot: str
) -> list[dict]:
    run_command(
        [
            audit_settings.CODEQL_BIN,
            "database",
            "analyze",
            str(database),
            str(pack / "generated.ql"),
            f"--additional-packs={search_paths(pack)}",
            "--format=sarif-latest",
            f"--output={output}",
            f"--threads={audit_settings.CODEQL_THREADS}",
            f"--ram={audit_settings.CODEQL_RAM}",
        ],
        log,
        audit_settings.SCAN_TIMEOUT,
    )
    return parse_sarif(output, snapshot)


def write_fixtures(directory: Path, language: str, fixture: dict) -> None:
    files = fixture.get("files", {})
    if (
        not files
        or len(files) > 20
        or sum(len(content) for content in files.values()) > 200000
    ):
        raise AuditError("正反样本必须提供有限源码文件")
    suffixes = {".py"} if language == "python" else {".js", ".jsx", ".ts", ".tsx"}
    for name, content in files.items():
        relative = Path(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or "\\" in name
            or ":" in name
            or relative.suffix not in suffixes
        ):
            raise AuditError("样本文件路径或类型无效")
        check_syntax(name, content)
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    for expected in fixture.get("expected", []):
        if (
            set(expected) != {"file", "line"}
            or expected["file"] not in files
            or not isinstance(expected["line"], int)
        ):
            raise AuditError("正样本预期位置无效")
        if not 1 <= expected["line"] <= len(files[expected["file"]].splitlines()):
            raise AuditError("正样本预期行超出源码范围")


def validate_fixtures(
    directory: Path, pack: Path, language: str, fixtures: dict
) -> dict:
    if not fixtures["positive"].get("expected") or fixtures["negative"].get("expected"):
        raise AuditError("正样本需要明确预期位置；反样本预期必须为空")
    scanner = CodeQLScanner()
    log = directory / "execution.log"
    compile_query(pack, log)
    checks = {}
    for kind in ["positive", "negative"]:
        root = directory / kind
        write_fixtures(root, language, fixtures[kind])
        database = directory / f"{kind}-database"
        scanner.create_database(root, database, log, ScanPlan(language, "", ""))
        findings = run_query(
            database, pack, directory / f"{kind}.sarif", log, f"fixture:{kind}"
        )
        actual = {
            (location["file"], location["line"])
            for finding in findings
            for location in finding["locations"]
        }
        expected = {(row["file"], row["line"]) for row in fixtures[kind]["expected"]}
        checks[kind] = {
            "status": "passed" if actual == expected else "failed",
            "expected": sorted(expected),
            "snapshot_hash": snapshot_digest(root),
            "actual": sorted(actual),
            "findings": findings,
        }
    return {
        "status": "passed"
        if all(check["status"] == "passed" for check in checks.values())
        else "failed",
        "compile": "passed",
        "tests": checks,
        "codeql_version": scanner.version(),
        "meaning": "approved fixture regression only; not a measured real-world precision claim",
    }
