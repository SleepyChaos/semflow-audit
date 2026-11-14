"""Algorithm extracted from app.adapters.codeql.rule_spec.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Experimental bounded specification -> pinned official detector template.

This is baseline reuse, not evidence of novel detection. Free QL remains a
separate experimental arm. No holdout data enters specification generation.
"""
import hashlib
import re
from typing import Literal
from uuid import UUID

from pydantic import Field
from semflow_contracts.modelio.stages import RuleResponse, StrictModel, TestFixture

from semflow_research.adapters.retrieval.rule_routing import operation_for
from semflow_research.domain.errors import AuditError


class DetectorSpec(StrictModel):
    language: Literal["python", "javascript"]
    operation: Literal["eval", "sql", "xss"]
    purpose: Literal["vulnerability_detector"]
    title: str = Field(min_length=1, max_length=200)
    coverage_analysis: str = Field(min_length=10, max_length=2000)
    knowledge_ids: list[UUID] = Field(min_length=1, max_length=20)
    positive: TestFixture
    negative: TestFixture


def detector_template(language, operation, *, _kernel):
    if language not in {"python", "javascript"} or operation not in {
        "eval",
        "sql",
        "xss",
    }:
        raise AuditError("受限规格原型暂不支持此语言或漏洞类型")
    spec = (
        _kernel.settings.PYTHON_QUERY_PACK
        if language == "python"
        else _kernel.settings.JAVASCRIPT_QUERY_PACK
    )
    name, version = spec.split("@")
    relative = {
        "eval": "Security/CWE-094/CodeInjection.ql",
        "sql": "Security/CWE-089/SqlInjection.ql",
        "xss": "Security/CWE-079/ReflectedXss.ql",
    }[operation]
    path = _kernel.settings.CODEQL_PACK_PATH / name / version / relative
    if not path.is_file():
        raise AuditError("固定检测模板不存在；不生成替代查询")
    raw = path.read_text()
    query = re.sub("@id\\s+\\S+", f"@id audit/{language}-{operation}-template", raw)
    return (
        query,
        {
            "source": f"codeql-pack:{spec}/{relative}",
            "sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "coverage": "baseline_reuse",
            "license": "MIT",
        },
    )


def generate_from_spec(provider, context, *, _kernel):
    if context["purpose"] != "vulnerability_detector":
        raise AuditError("受限规格原型只支持 detector；anchor/framework 计为不支持")
    operation = operation_for(context["requirement"])
    query, provenance = detector_template(
        context["language"], operation, _kernel=_kernel
    )
    spec = provider.generate(
        "rule",
        {
            **context,
            "generation_mode": "detector_spec",
            "allowed_spec": {"language": context["language"], "operation": operation},
            "template_provenance": provenance,
        },
        DetectorSpec,
    )
    if (spec.language, spec.operation) != (context["language"], operation):
        raise AuditError("规格语言/操作与需求不匹配")
    response = RuleResponse(
        purpose=spec.purpose,
        title=spec.title,
        strategy="new_query",
        coverage_analysis="[baseline_reuse] " + spec.coverage_analysis,
        query=query,
        modules={},
        knowledge_ids=spec.knowledge_ids,
        positive=spec.positive,
        negative=spec.negative,
    )
    return (response, provenance)
