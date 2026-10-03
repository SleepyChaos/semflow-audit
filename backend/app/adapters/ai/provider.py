"""Configured OpenAI-compatible provider. No simulated responses in application code."""

import json
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import TypeVar

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from app.adapters.ai.policy import CallBudget, policy_snapshot
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
        self.policy = policy_snapshot()
        self.records = []
        self.prompt_version = "1"
        self.budget = CallBudget(self.policy, self.records)
        self.persist = lambda: None
        self.response_directory = None
        self.prompt_snapshot = None
        self.client = OpenAI(
            base_url=audit_settings.AI_BASE_URL,
            api_key=audit_settings.AI_API_KEY.get_secret_value() or "local-provider",
            timeout=audit_settings.AI_TIMEOUT,
            max_retries=0,
        )

    def bind_stage(self, stage_id: str, prompt_version: str = "1") -> None:
        from app.persistence.stage_repository import StageRepository

        repository = StageRepository()
        from app.adapters.artifacts import ArtifactStore

        self.response_directory = ArtifactStore().directory(stage_id)
        stage = repository.get(stage_id)
        self.policy = stage.model_config_snapshot or policy_snapshot()
        version = prompt_version if stage.kind in {"rule", "review"} else "1"
        self.prompt_snapshot = self.policy.get("prompt_snapshot")
        if self.prompt_snapshot is None:
            prompt = (PROMPTS / f"{stage.kind}.v{version}.txt").read_text()
            self.prompt_snapshot = {
                "purpose": stage.kind,
                "version": version,
                "content": prompt,
                "sha256": sha256(prompt.encode()).hexdigest(),
            }
            self.policy = {**self.policy, "prompt_snapshot": self.prompt_snapshot}
        if (
            self.prompt_snapshot["purpose"] != stage.kind
            or self.prompt_snapshot["version"] != version
            or sha256(self.prompt_snapshot["content"].encode()).hexdigest()
            != self.prompt_snapshot["sha256"]
        ):
            raise AuditError("阶段提示词快照不匹配，不能恢复生成")
        self.model = self.policy["model"]
        self.client.base_url = self.policy["base_url"]
        if stage.usage:
            self.usage = dict(stage.usage)
        self.records = list(stage.model_calls)
        self.prompt_version = prompt_version
        self.budget = CallBudget(self.policy, self.records)
        self.persist = lambda: repository.update(
            stage_id,
            model_config_snapshot=self.policy,
            model_calls=list(self.records),
            usage=dict(self.usage),
        )
        self.persist()

    def generate(self, purpose: str, payload: dict, schema: type[Response]) -> Response:
        if not self.model:
            raise AuditError("未配置 AI_MODEL")
        version = self.prompt_version if purpose in {"review", "rule"} else "1"
        if self.prompt_snapshot is not None:
            if (purpose, version) != (
                self.prompt_snapshot["purpose"],
                self.prompt_snapshot["version"],
            ):
                raise AuditError("阶段模型调用越过提示词范围")
            prompt = self.prompt_snapshot["content"]
        else:
            prompt = (PROMPTS / f"{purpose}.v{version}.txt").read_text()
        messages = [
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
        ]
        output = self.policy["budgets"][purpose]
        for attempt in range(2):
            input_bound = len(json.dumps(messages, ensure_ascii=False).encode()) + 256
            timeout = self.budget.reserve(output, input_bound)
            record = {
                "purpose": purpose,
                "call_index": len(self.records) + 1,
                "input_hash": sha256(
                    json.dumps(payload, sort_keys=True).encode()
                ).hexdigest(),
                "reserved_tokens": input_bound + output,
                "attempt": attempt + 1,
                "prompt_version": version,
                "prompt_hash": sha256(prompt.encode()).hexdigest(),
                "schema_hash": sha256(
                    json.dumps(schema.model_json_schema(), sort_keys=True).encode()
                ).hexdigest(),
                "request_model": self.model,
                "output_budget": output,
                "input_tokens": None,
                "output_tokens": None,
                "reasoning_tokens": None,
                "finish_reason": None,
                "response_model": None,
                "error_code": None,
            }
            start = monotonic()
            error = None
            result = None
            self.usage["calls"] += 1
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    max_tokens=output,
                    timeout=timeout,
                    extra_body={"thinking": {"type": self.policy["thinking_mode"]}}
                    if self.policy.get("thinking_mode")
                    else None,
                    response_format={"type": "json_object"},
                    messages=messages,
                )
                if self.response_directory is not None:
                    content = (
                        completion.choices[0].message.content
                        if completion.choices
                        else None
                    )
                    if content is not None:
                        # Preserve incomplete/schema-invalid candidates privately, never log raw output.
                        name = f"model-call-{record['call_index']}.response.txt"
                        (self.response_directory / name).write_text(content[:200000])
                        record["response_artifact"] = name
                        record["response_artifact_truncated"] = len(content) > 200000
                record["response_model"] = completion.model
                if completion.usage:
                    record["input_tokens"] = completion.usage.prompt_tokens
                    record["output_tokens"] = completion.usage.completion_tokens
                    details = completion.usage.completion_tokens_details
                    record["reasoning_tokens"] = (
                        details.reasoning_tokens if details else None
                    )
                    self.usage["input_tokens"] += completion.usage.prompt_tokens
                    self.usage["output_tokens"] += completion.usage.completion_tokens
                record["finish_reason"] = (
                    completion.choices[0].finish_reason if completion.choices else None
                )
                if record["finish_reason"] != "stop":
                    record["error_code"] = (
                        "length"
                        if record["finish_reason"] == "length"
                        else "incomplete"
                    )
                    error = AuditError("模型输出不完整；结论未知")
                else:
                    result = schema.model_validate_json(
                        completion.choices[0].message.content or ""
                    )
            except OpenAIError as exc:
                record["error_code"] = (
                    "timeout"
                    if type(exc).__name__ == "APITimeoutError"
                    else "provider_error"
                )
                error = AuditError(
                    f"模型服务请求失败（{type(exc).__name__}）；检查服务配置"
                )
            except ValidationError:
                record["error_code"] = "schema_invalid"
                error = AuditError("模型输出不符合结构契约；未确认任何漏洞")
            finally:
                if record["input_tokens"] is None or record["output_tokens"] is None:
                    self.usage["unknown_usage_calls"] = (
                        self.usage.get("unknown_usage_calls", 0) + 1
                    )
                record["seconds"] = monotonic() - start
                self.records.append(record)
                self.persist()
            if result is not None:
                return result
            if (
                attempt == 0
                and record["error_code"] == "length"
                and record["input_tokens"] is not None
            ):
                output *= 2
                continue
            if attempt == 0 and record["error_code"] == "schema_invalid":
                messages = [
                    *messages,
                    {
                        "role": "user",
                        "content": "The previous response failed the supplied JSON schema. Regenerate the complete response using only the original evidence and schema. Do not invent missing evidence or locations.",
                    },
                ]
                continue
            error.code = record["error_code"]
            raise error
        raise AuditError("模型恢复预算耗尽")

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
