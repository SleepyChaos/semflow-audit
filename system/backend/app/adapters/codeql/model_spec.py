"""Experimental typed Python sink models using verified CodeQL extension points."""

import json
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.adapters.codeql.rule_spec import detector_template
from app.contracts.stages import RuleResponse, StrictModel, TestFixture
from app.domain.audit import AuditError


class SinkSpec(StrictModel):
    module: str = Field(
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*){0,3}$",
        max_length=100,
    )
    member: str = Field(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$", max_length=100)
    argument: int = Field(ge=0, le=4, strict=True)
    evidence_id: UUID


class FrameworkSpec(StrictModel):
    language: Literal["python"]
    operation: Literal["eval"]
    purpose: Literal["vulnerability_detector"]
    title: str = Field(min_length=1, max_length=200)
    coverage_analysis: str = Field(min_length=10, max_length=2000)
    sinks: list[SinkSpec] = Field(min_length=1, max_length=4)
    knowledge_ids: list[UUID] = Field(min_length=1, max_length=20)
    positive: TestFixture
    negative: TestFixture


def generate_framework_spec(provider, context, artifact_path=None):
    if (
        context["language"] != "python"
        or context["purpose"] != "vulnerability_detector"
    ):
        raise AuditError("受限框架模型原型只支持 Python 代码注入检测")
    response = provider.generate(
        "rule", {**context, "generation_mode": "framework_spec"}, FrameworkSpec
    )
    if artifact_path is not None:
        artifact_path.write_text(
            json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2)
        )
    available = {row["id"]: row["content"] for row in context["knowledge"]}
    for sink in response.sinks:
        evidence = available.get(str(sink.evidence_id), "")
        if sink.module not in evidence or sink.member not in evidence:
            raise AuditError("框架模型符号没有实际检索证据")
    modules = []
    for index, sink in enumerate(response.sinks):
        expression = f'API::moduleImport("{sink.module}").getMember("{sink.member}").getACall().getArg({sink.argument})'
        modules.append(
            f"class ModelSink{index} extends CodeInjection::Sink {{\n  ModelSink{index}() {{ this = {expression} }}\n}}"
        )
    module = (
        "import python\nimport semmle.python.ApiGraphs\nimport semmle.python.security.dataflow.CodeInjectionCustomizations\n\n"
        + "\n\n".join(modules)
        + "\n"
    )
    query, provenance = detector_template("python", "eval")
    query = query.replace(
        "import python\n", "import python\nimport FrameworkModel\n", 1
    )
    provenance = {
        **provenance,
        "coverage": "custom_sink_extension",
        "grammar": "python-code-injection-sink-v1",
    }
    return RuleResponse(
        purpose=response.purpose,
        title=response.title,
        strategy="new_query",
        coverage_analysis=response.coverage_analysis,
        query=query,
        modules={"FrameworkModel.qll": module},
        knowledge_ids=list(
            dict.fromkeys(
                [
                    *response.knowledge_ids,
                    *[sink.evidence_id for sink in response.sinks],
                ]
            )
        ),
        positive=response.positive,
        negative=response.negative,
    ), provenance
