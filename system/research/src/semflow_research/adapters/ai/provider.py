"""Frozen model adapter: explicit inputs and durable calls, no platform binding."""

import json
import math
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import TypeVar
from uuid import uuid4

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from semflow_research.adapters.ai.policy import CallBudget
from semflow_research.domain.errors import AuditError
from semflow_research.runtime.calls import CallJournal

Response = TypeVar("Response", bound=BaseModel)
PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


class CompatibleModel:
    def for_execution(self, context):
        """Rebind frozen prompts, reservations and usage to a planned child."""
        return type(self)(_kernel=context)

    def __init__(self, *, _kernel):
        self.context = _kernel
        record = _kernel.execution_records.get(_kernel.execution_id)
        self.policy = dict(record.policy)
        self.model = self.policy["model"]
        self.records = list(record.model_calls)
        self.usage = dict(
            record.usage or {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        )
        self.method_version = record.method_version
        self.prompts = {}
        for prompt in _kernel.spec.prompts:
            raw = _kernel.artifacts.read(prompt.content)
            if sha256(raw).hexdigest() != prompt.sha256:
                raise AuditError("冻结 Prompt 摘要不匹配", code="integrity_error")
            self.prompts[prompt.role] = {
                "purpose": prompt.role,
                "version": prompt.version,
                "content": raw.decode("utf-8"),
                "sha256": prompt.sha256,
            }
        self.budget = CallBudget(self.policy, self.records)
        self.journal = CallJournal(
            _kernel.executions,
            _kernel.budget_owner_id or _kernel.execution_id,
            _kernel.execution_id,
        )
        self.response_directory = _kernel.workspace
        self.prompt_snapshot = None
        if not _kernel.settings.AI_BASE_URL:
            raise AuditError("模型 endpoint profile 未装配", code="model_unavailable")
        self.client = OpenAI(
            base_url=_kernel.settings.AI_BASE_URL,
            api_key=_kernel.settings.AI_API_KEY.get_secret_value() or "local-provider",
            timeout=_kernel.settings.AI_TIMEOUT,
            max_retries=0,
        )

    def persist(self):
        self.context.execution_records.update(
            self.context.execution_id,
            model_calls=list(self.records),
            usage=dict(self.usage),
        )

    def generate(self, purpose: str, payload: dict, schema: type[Response]) -> Response:
        _kernel = self.context
        snapshot = self.prompts.get(purpose)
        if snapshot is None:
            raise AuditError("模型用途没有冻结 Prompt", code="integrity_error")
        self.prompt_snapshot = snapshot
        if not self.model:
            raise AuditError("未配置 AI_MODEL")
        version = snapshot["version"]
        prompt = snapshot["content"]
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
        for attempt in range(self.context.spec.policy.max_attempts):
            validation_feedback = None
            input_bound = len(json.dumps(messages, ensure_ascii=False).encode()) + 256
            timeout = self.budget.reserve(output, input_bound)
            call_id = uuid4()
            timeout = min(
                timeout,
                self.journal.reserve(
                    call_id,
                    input_digest=sha256(
                        json.dumps(messages, sort_keys=True).encode()
                    ).hexdigest(),
                    reserved_tokens=input_bound + output,
                ),
            )
            record = {
                "purpose": purpose,
                "call_index": len(self.records) + 1,
                "input_hash": sha256(
                    json.dumps(payload, sort_keys=True).encode()
                ).hexdigest(),
                "reserved_tokens": input_bound + output,
                "input_bound_method": "utf8_bytes_upper_bound",
                "attempt": attempt + 1,
                # Interface peer: state.repositories.ExecutionRecords.update.
                # AGENT: algorithm and Prompt revisions are separate identities;
                # preserve both even when their labels happened to be equal before.
                "method_version": _kernel.spec.implementation.method_version,
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
                "cached_input_tokens": None,
                "finish_reason": None,
                "response_model": None,
                "error_code": None,
                "timeout_seconds": timeout,
            }
            start = monotonic()
            record["call_id"] = str(call_id)
            error = None
            result = None
            completion = None
            self.usage["calls"] += 1
            try:
                # WIRE-SEND:research.model_exchange — peer: model schema receiver below / frozen_call.
                # AGENT: keep prompt, output schema, request budgets and the receiver's
                # evidence/unknown-premise semantics aligned; model text grants no human decision.
                completion = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=output,
                    timeout=timeout,
                    extra_body={"thinking": {"type": self.policy["thinking_mode"]}}
                    if self.policy.get("thinking_mode")
                    else None,
                    response_format={"type": "json_object"},
                    messages=messages,
                    **(
                        {"temperature": self.policy["temperature"]}
                        if self.policy.get("temperature") is not None
                        else {}
                    ),
                )
                response_ref = _kernel.artifacts.commit(
                    completion.model_dump_json().encode(),
                    kind="model_call",
                    schema_version="semflow.model-response/1",
                )
                record["response_ref"] = response_ref.model_dump(mode="json")
                if self.response_directory is not None:
                    content = (
                        completion.choices[0].message.content
                        if completion.choices
                        else None
                    )
                    if content is not None:
                        name = f"model-call-{record['call_index']}.response.txt"
                        (self.response_directory / name).write_text(
                            content[:200000], encoding="utf-8"
                        )
                        record["response_artifact"] = name
                        record["response_artifact_truncated"] = len(content) > 200000
                record["response_model"] = completion.model
                if completion.usage:
                    record["input_tokens"] = completion.usage.prompt_tokens
                    record["output_tokens"] = completion.usage.completion_tokens
                    prompt_details = completion.usage.prompt_tokens_details
                    record["cached_input_tokens"] = (
                        prompt_details.cached_tokens if prompt_details else None
                    )
                    details = completion.usage.completion_tokens_details
                    record["reasoning_tokens"] = (
                        details.reasoning_tokens if details else None
                    )
                    self.usage["input_tokens"] += completion.usage.prompt_tokens
                    self.usage["output_tokens"] += completion.usage.completion_tokens
                record["finish_reason"] = (
                    completion.choices[0].finish_reason if completion.choices else None
                )
                if (
                    _kernel.spec.model.revision is not None
                    and completion.model != _kernel.spec.model.revision
                ):
                    record["error_code"] = "model_output_invalid"
                    raise AuditError(
                        "模型响应版本与冻结 revision 不同", code="model_output_invalid"
                    )
                if record["finish_reason"] != "stop":
                    record["error_code"] = (
                        "length"
                        if record["finish_reason"] == "length"
                        else "incomplete"
                    )
                    error = AuditError("模型输出不完整；结论未知")
                else:
                    # WIRE-RECV:research.model_exchange — peer: request above / frozen_call.
                    # AGENT: structure is checked here; evidence and source identity are
                    # checked by the caller. Never interpret schema validity as correctness.
                    result = schema.model_validate_json(
                        completion.choices[0].message.content or ""
                    )
            except OpenAIError as exc:
                from semflow_research.adapters.ai.provider_failures import (
                    failure_details,
                )

                record.update(failure_details(exc, self.client.base_url))
                record["error_code"] = (
                    "timeout"
                    if type(exc).__name__ == "APITimeoutError"
                    else "rate_limited"
                    if type(exc).__name__ == "RateLimitError"
                    else "provider_error"
                )
                if record["error_code"] == "rate_limited":
                    record["retry_after"] = (
                        str(record["retry_after_seconds"])
                        if record["retry_after_seconds"] is not None
                        else None
                    )
                error = AuditError(
                    "模型服务限流；进度已保留，额度恢复后可继续审计"
                    if record["error_code"] == "rate_limited"
                    else f"模型服务请求失败（{type(exc).__name__}）；检查服务配置"
                )
            except ValidationError as exc:
                validation_feedback = [
                    {
                        "location": list(row["loc"]),
                        "type": row["type"],
                        "message": row["msg"][:500],
                    }
                    for row in exc.errors(include_input=False, include_url=False)[:12]
                ]
                record["validation_feedback"] = validation_feedback
                if (
                    completion
                    and completion.choices
                    and purpose == "scout"
                    and getattr(
                        getattr(_kernel.spec.inputs, "window_policy", None),
                        "version",
                        None,
                    )
                    == "2"
                ):
                    from semflow_research.adapters.ai.scout_response import (
                        recover_display_fields,
                    )

                    result = recover_display_fields(
                        completion.choices[0].message.content or "", schema, exc
                    )
                if result is not None:
                    record["recovery_class"] = "revalidated_display_fields"
                else:
                    record["error_code"] = "schema_invalid"
                    record["recovery_class"] = "bounded_schema_retry"
                    error = AuditError("模型输出不符合结构契约；未确认任何漏洞")
                    error.validation_feedback = validation_feedback
            finally:
                if record["input_tokens"] is None or record["output_tokens"] is None:
                    self.usage["unknown_usage_calls"] = (
                        self.usage.get("unknown_usage_calls", 0) + 1
                    )
                record["seconds"] = monotonic() - start
                self.journal.finish(
                    call_id,
                    record,
                    outcome="known" if completion is not None else "unknown",
                )
                self.records.append(record)
                self.persist()
            if result is not None:
                return result
            if (
                attempt + 1 < self.context.spec.policy.max_attempts
                and record["error_code"] == "schema_invalid"
            ):
                messages = [
                    *messages,
                    {
                        "role": "user",
                        "content": "The previous response failed validation. Correct the complete response using only original evidence. Preserve unresolved premises: choose insufficient/pending when a supported/excluded verdict conflicts with them; do not remove unknowns to make a verdict pass. Do not invent evidence or locations. Diagnostics: "
                        + json.dumps(validation_feedback, ensure_ascii=False),
                    },
                ]
                continue
            error.code = record["error_code"]
            raise error
        raise AuditError("模型恢复预算耗尽")

    def embed(self, texts: list[str]) -> list[list[float]]:
        _kernel = self.context
        if not _kernel.settings.EMBEDDING_MODEL:
            raise AuditError("未配置 EMBEDDING_MODEL")
        try:
            result = self.client.embeddings.create(
                model=_kernel.settings.EMBEDDING_MODEL,
                input=texts,
                encoding_format="float",
                **{"dimensions": _kernel.settings.EMBEDDING_DIMENSIONS}
                if _kernel.settings.EMBEDDING_DIMENSIONS
                else {},
            )
            if (
                _kernel.settings.EMBEDDING_REVISION
                and result.model != _kernel.settings.EMBEDDING_REVISION
            ):
                raise AuditError("向量模型服务版本变化，请核实版本后重新索引")
            if [
                row.index for row in sorted(result.data, key=lambda row: row.index)
            ] != list(range(len(texts))):
                raise AuditError("向量返回索引不完整或重复")
            vectors = [
                row.embedding for row in sorted(result.data, key=lambda row: row.index)
            ]
            if (
                any(
                    not vector
                    or not all(math.isfinite(value) for value in vector)
                    or (not any(vector))
                    or (
                        _kernel.settings.EMBEDDING_DIMENSIONS
                        and len(vector) != _kernel.settings.EMBEDDING_DIMENSIONS
                    )
                    for vector in vectors
                )
                or len({len(v) for v in vectors}) != 1
            ):
                raise AuditError("向量返回维度或数值无效")
            return vectors
        except OpenAIError as exc:
            raise AuditError("向量服务请求失败；不降级伪造向量") from exc
