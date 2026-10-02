from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class AuditSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    ARTIFACT_ROOT: Path = ROOT / "artifacts"
    CODEQL_BIN: str = "codeql"
    CODEQL_PYTHON_BIN: str = "python3.11"
    CODEQL_PACK_PATH: Path = ROOT / "artifacts/packs"
    PYTHON_QUERY_PACK: str = "codeql/python-queries@1.6.0"
    JAVASCRIPT_QUERY_PACK: str = "codeql/javascript-queries@1.4.0"
    REDIS_URL: str = "redis://127.0.0.1:6389/0"
    UPLOAD_LIMIT: int = 20 * 1024 * 1024
    EXTRACT_LIMIT: int = 100 * 1024 * 1024
    FILE_LIMIT: int = 2000
    SCAN_TIMEOUT: int = 900
    CODEQL_THREADS: int = 2
    CODEQL_RAM: int = 2048


audit_settings = AuditSettings()
