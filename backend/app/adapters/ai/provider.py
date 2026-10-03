"""Configured OpenAI-compatible provider. No simulated responses in application code."""

import json
from pathlib import Path
from typing import TypeVar

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from app.core.audit_config import audit_settings
from app.domain.audit import AuditError

Response = TypeVar("Response", bound=BaseModel)
PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


class CompatibleModel:
    def __init__(self):
        self.model = audit_settings.AI_MODEL
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        if not audit_settings.AI_BASE_URL:
            raise AuditError("未配置 AI_MODEL / AI_BASE_URL；不会产生模拟审计结果")
        self.client = OpenAI(
            base_url=audit_settings.AI_BASE_URL,
            api_key=audit_settings.AI_API_KEY.get_secret_value() or "local-provider",
            timeout=audit_settings.AI_TIMEOUT,
            max_retries=0,
        )

    def generate(self, purpose: str, payload: dict, schema: type[Response]) -> Response:
        if not self.model:
            raise AuditError("未配置 AI_MODEL")
        prompt = (PROMPTS / f"{purpose}.v1.txt").read_text()
        self.usage["calls"] += 1
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                max_tokens=audit_settings.AI_MAX_OUTPUT_TOKENS,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": prompt
                        + "\nReturn JSON matching this schema:\n"
                        + json.dumps(schema.model_json_schema()),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"untrusted_analysis_material": payload}, ensure_ascii=False
                        ),
                    },
                ],
            )
            if completion.usage:
                self.usage["input_tokens"] += completion.usage.prompt_tokens
                self.usage["output_tokens"] += completion.usage.completion_tokens
            if not completion.choices or completion.choices[0].finish_reason != "stop":
                raise AuditError("模型输出不完整；请减少范围或提高输出预算")
            return schema.model_validate_json(
                completion.choices[0].message.content or ""
            )
        except OpenAIError as exc:
            raise AuditError(
                f"模型服务请求失败（{type(exc).__name__}）；检查服务配置"
            ) from exc
        except ValidationError as exc:
            raise AuditError(
                "模型输出不符合结构契约；本阶段失败，未确认任何漏洞"
            ) from exc

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not audit_settings.EMBEDDING_MODEL:
            raise AuditError("未配置 EMBEDDING_MODEL")
        try:
            result = self.client.embeddings.create(
                model=audit_settings.EMBEDDING_MODEL, input=texts
            )
            return [
                row.embedding for row in sorted(result.data, key=lambda row: row.index)
            ]
        except OpenAIError as exc:
            raise AuditError("向量服务请求失败；不降级伪造向量") from exc
