"""Explicit tool resources for one research invocation; never a BaseSettings singleton."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from semflow_contracts.wire import schema_meaning


class ToolSettings(BaseModel):
    # Interface peers: factory.assemble resource snapshot sender / receiver.
    # AGENT: snapshot serialization excludes credentials; change both resource
    # resolution and restart verification when changing a tool/profile meaning.
    model_config = ConfigDict(
        extra="forbid", frozen=True, json_schema_extra=schema_meaning("resources")
    )
    ARTIFACT_ROOT: Path
    CODEQL_BIN: str
    CODEQL_PYTHON_BIN: str
    CODEQL_PACK_PATH: Path
    PYTHON_QUERY_PACK: str
    JAVASCRIPT_QUERY_PACK: str
    SCAN_TIMEOUT: int = Field(ge=1)
    CODEQL_THREADS: int = Field(ge=1)
    CODEQL_RAM: int = Field(ge=1)
    VALIDATOR_PYTHON_IMAGE: str
    VALIDATOR_JS_IMAGE: str
    VALIDATOR_TIMEOUT: int = Field(ge=1)
    SEMANTIC_CONTEXT_CHARS: int = Field(ge=1)
    SEMANTIC_REPAIR_MAX_CONTEXT_CHARS: int = Field(ge=1)
    SEMANTIC_TOOL_LIMIT: int = Field(ge=1)
    REPAIR_SOURCE_TOOL_LIMIT: int = Field(ge=1)
    REPAIR_INITIAL_SOURCE_TOOL_LIMIT: int = Field(ge=1)
    REPAIR_MODEL_CALL_LIMIT: int = Field(ge=1)
    REPAIR_ATTEMPTS: int = Field(ge=1)
    REVIEW_QUERY_LIMIT: int = Field(ge=1)
    AI_BASE_URL: str = ""
    AI_API_KEY: SecretStr = Field(default=SecretStr(""), exclude=True)
    AI_MODEL: str = ""
    AI_TIMEOUT: int = Field(default=90, ge=1)
    AI_MAX_OUTPUT_TOKENS: int = Field(default=6000, ge=1)
    AI_REVIEW_TOKENS: int = Field(default=0, ge=0)
    AI_SCOUT_TOKENS: int = Field(default=0, ge=0)
    AI_REPAIR_TOKENS: int = Field(default=0, ge=0)
    AI_RULE_TOKENS: int = Field(default=0, ge=0)
    AI_AUDIT_EXECUTION_MODE: str = "bounded"
    AI_STAGE_MAX_CALLS: int = Field(default=24, ge=1)
    AI_STAGE_MAX_TOKENS: int = Field(default=100000, ge=1)
    AI_STAGE_MAX_SECONDS: int = Field(default=300, ge=1)
    AI_STAGE_MAX_NO_PROGRESS: int = Field(default=3, ge=1)
    AI_THINKING_MODE: str | None = None
    EMBEDDING_MODEL: str = ""
    EMBEDDING_REVISION: str = ""
    EMBEDDING_DIMENSIONS: int = Field(default=0, ge=0)
    OPENHANDS_PYTHON: str = ""
    OPENHANDS_IMAGE: str = ""
    OPENHANDS_BASE_URL: str = ""
    OPENHANDS_API_KEY: SecretStr = Field(default=SecretStr(""), exclude=True)
    OPENHANDS_MAX_STEPS: int = Field(default=100, ge=1)
    OPENHANDS_RUNNER: Path | None = None
    # Peer: factory.assemble -> openhands_resources.stage_worker. AGENT: this
    # binds copied worker bytes, not just a mutable runner path, across restarts.
    OPENHANDS_WORKER_IDENTITY: dict[str, str] | None = None
    CODEQL_LSP_CLIENT: Path | None = None
