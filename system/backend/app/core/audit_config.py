from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[4]


class AuditSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    ARTIFACT_ROOT: Path = ROOT / "artifacts"
    CODEQL_BIN: str = "codeql"
    CODEQL_PYTHON_BIN: str = "python3.11"
    CODEQL_PACK_PATH: Path = ROOT / "artifacts/packs"
    PYTHON_QUERY_PACK: str = "codeql/python-queries@1.6.0"
    JAVASCRIPT_QUERY_PACK: str = "codeql/javascript-queries@1.4.0"
    REDIS_URL: str = "redis://127.0.0.1:16380/0"
    UPLOAD_LIMIT: int = 20 * 1024 * 1024
    EXTRACT_LIMIT: int = 100 * 1024 * 1024
    FILE_LIMIT: int = 2000
    SCAN_TIMEOUT: int = 900
    CODEQL_THREADS: int = 2
    CODEQL_RAM: int = 2048
    AI_BASE_URL: str = ""
    AI_API_KEY: SecretStr = SecretStr("")
    AI_MODEL: str = ""
    AI_TIMEOUT: int = 90
    AI_MAX_OUTPUT_TOKENS: int = 6000
    AI_REVIEW_TOKENS: int = 0
    AI_SCOUT_TOKENS: int = 3000
    AI_REPAIR_TOKENS: int = 0
    AI_RULE_TOKENS: int = 0
    AI_THINKING_MODE: Literal["enabled", "disabled"] | None = None
    AI_STAGE_MAX_CALLS: int = 24
    AI_STAGE_MAX_TOKENS: int = 100000
    AI_STAGE_MAX_SECONDS: int = 300
    AI_AUDIT_EXECUTION_MODE: Literal["bounded", "progress"] = "progress"
    AI_STAGE_MAX_NO_PROGRESS: int = 3
    EMBEDDING_MODEL: str = ""
    EMBEDDING_REVISION: str = ""
    EMBEDDING_DIMENSIONS: int = 0
    SEMANTIC_CONTEXT_CHARS: int = 40000
    SEMANTIC_REPAIR_MAX_CONTEXT_CHARS: int = 80000
    SEMANTIC_TOOL_LIMIT: int = 8
    REPAIR_ATTEMPTS: int = 3
    VALIDATOR_PYTHON_IMAGE: str = "ai-code-audit-validator:local"
    VALIDATOR_JS_IMAGE: str = "node:22-bookworm-slim"
    VALIDATOR_TIMEOUT: int = 120
    REVIEW_QUERY_LIMIT: int = 3


audit_settings = AuditSettings()
