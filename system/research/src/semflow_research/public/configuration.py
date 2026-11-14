"""Explicit research resource profiles; credentials never enter RunSpec/artifacts."""

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from semflow_contracts.errors import ResearchError

from semflow_research.runtime.settings import ToolSettings


class ModelEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    base_url: str = Field(min_length=1)
    api_key_env: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")


class ResourceFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    profile_id: str
    settings: dict
    model_endpoints: dict[str, ModelEndpoint] = Field(default_factory=dict)


def load_resources(path: Path, spec, *, root: Path, environment=None) -> ToolSettings:
    environment = os.environ if environment is None else environment
    resource = ResourceFile.model_validate_json(path.read_bytes())
    if resource.profile_id != spec.policy.resource_profile:
        raise ResearchError(
            "identity_mismatch", "Resource profile does not match the frozen request"
        )
    forbidden = {
        "AI_API_KEY",
        "AI_BASE_URL",
        "AI_MODEL",
        "ARTIFACT_ROOT",
        "OPENHANDS_API_KEY",
    }
    if forbidden & resource.settings.keys() or resource.settings.get(
        "OPENHANDS_BASE_URL"
    ):
        raise ResearchError(
            "invalid_contract",
            "Resource settings must use endpoint profiles and secret environment references",
        )
    endpoint, key = "", ""
    if spec.model is not None:
        selected = resource.model_endpoints.get(spec.model.endpoint_profile)
        if selected is None:
            raise ResearchError(
                "model_unavailable",
                "Requested research model endpoint profile is not configured",
            )
        endpoint = selected.base_url
        if selected.api_key_env:
            key = environment.get(selected.api_key_env, "")
            if not key:
                raise ResearchError(
                    "model_unavailable",
                    "Research endpoint credential environment reference is unavailable",
                )
    settings = dict(resource.settings)
    hands = getattr(spec.inputs, "openhands", None)
    if hands is not None:
        selected = resource.model_endpoints.get(hands.endpoint_profile)
        if selected is None:
            raise ResearchError(
                "model_unavailable", "OpenHands endpoint profile is not configured"
            )
        hands_key = (
            environment.get(selected.api_key_env, "") if selected.api_key_env else ""
        )
        if selected.api_key_env and not hands_key:
            raise ResearchError(
                "model_unavailable", "OpenHands endpoint credential is unavailable"
            )
        settings.update(
            OPENHANDS_BASE_URL=selected.base_url, OPENHANDS_API_KEY=SecretStr(hands_key)
        )
    settings.update(
        ARTIFACT_ROOT=root,
        AI_BASE_URL=endpoint,
        AI_API_KEY=SecretStr(key),
        AI_MODEL=spec.model.model if spec.model else "",
        AI_TIMEOUT=spec.policy.per_call_timeout_seconds,
        SCAN_TIMEOUT=spec.policy.tool_timeout_seconds,
        VALIDATOR_TIMEOUT=spec.policy.tool_timeout_seconds,
    )
    return ToolSettings.model_validate(settings)
