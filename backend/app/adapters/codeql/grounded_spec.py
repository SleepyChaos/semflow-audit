"""Typed detector generation with a source extension grounded in read project code."""

import ast
import re
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.adapters.codeql.rule_spec import DetectorSpec, detector_template
from app.adapters.retrieval.rule_routing import operation_for
from app.contracts.stages import RuleResponse, StrictModel
from app.domain.audit import AuditError


class ExternalSource(StrictModel):
    module: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=100)
    member: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=100)
    source_evidence_id: UUID
    trust_evidence_id: UUID


class GroundedDetectorSpec(DetectorSpec):
    source_model: Literal["baseline", "python_external_call_return"]
    sources: list[ExternalSource] = Field(default_factory=list, max_length=4)


def verify_source(source, context):
    evidence = {row["id"]: row for row in context["semantic_inspection"]["evidence"]}
    row = evidence.get(str(source.source_evidence_id))
    trust = evidence.get(str(source.trust_evidence_id))
    if (
        not row
        or row["kind"] != "code"
        or not row["reference"].get("file", "").endswith(".py")
    ):
        raise AuditError("source 扩展必须引用已读取的 Python 源码")
    if row["reference"].get("start_line") != 1:
        raise AuditError("source 扩展需完整导入及调用窗口，不能猜测导入绑定")
    try:
        tree = ast.parse(row["content"])
    except SyntaxError as exc:
        raise AuditError("source 扩展证据窗口无法解析") from exc
    aliases, direct = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases.update(
                a.asname or a.name for a in node.names if a.name == source.module
            )
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == source.module
            and not node.level
        ):
            direct.update(
                a.asname or a.name for a in node.names if a.name == source.member
            )
    matched = any(
        isinstance(n, ast.Call)
        and (
            isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id in aliases
            and n.func.attr == source.member
            or isinstance(n.func, ast.Name)
            and n.func.id in direct
        )
        for n in ast.walk(tree)
    )
    if not matched:
        raise AuditError("模型 source API 不存在于实际导入和调用源码")
    if (
        not trust
        or source.module not in trust["content"]
        or source.member not in trust["content"]
        or not re.search(r"untrusted|不可信", trust["content"], re.I)
    ):
        raise AuditError("外部不可信 source 的业务依据不足，不能把任意调用标为污染源")
    knowledge = "\n".join(r["content"] for r in context["knowledge"])
    if not all(
        token in knowledge
        for token in ("moduleImport", "getMember", "getACall", "class Source")
    ):
        raise AuditError("检索材料缺少 source 扩展的实际 API 声明")


def render_spec(spec, context):
    operation = operation_for(context["requirement"])
    if (spec.language, spec.operation) != (context["language"], operation):
        raise AuditError("受限规格语言/漏洞类别与需求不符")
    if not set(map(str, spec.knowledge_ids)).issubset(
        {r["id"] for r in context["knowledge"]}
    ):
        raise AuditError("受限规格引用未检索知识")
    query, provenance = detector_template(spec.language, operation)
    modules = {}
    if spec.source_model == "baseline":
        if spec.sources:
            raise AuditError("baseline 规格不能携带未使用的 source")
    else:
        if (spec.language, operation) != ("python", "eval") or not spec.sources:
            raise AuditError("受限 source 扩展目前仅支持 Python eval 外部调用返回值")
        for source in spec.sources:
            verify_source(source, context)
        classes = [
            f'class ProjectSource{i} extends CodeInjection::Source {{\n  ProjectSource{i}() {{ this = API::moduleImport("{source.module}").getMember("{source.member}").getACall() }}\n}}'
            for i, source in enumerate(spec.sources)
        ]
        modules["ProjectCodeInjectionSources.qll"] = (
            "import python\nimport semmle.python.ApiGraphs\nimport semmle.python.security.dataflow.CodeInjectionCustomizations\n\n"
            + "\n\n".join(classes)
            + "\n"
        )
        query = query.replace(
            "import python\n", "import python\nimport ProjectCodeInjectionSources\n", 1
        )
        provenance = {
            **provenance,
            "coverage": "custom_source_extension",
            "sources": [s.model_dump(mode="json") for s in spec.sources],
        }
    return RuleResponse(
        purpose=spec.purpose,
        title=spec.title,
        strategy="new_query",
        coverage_analysis=f"[{provenance['coverage']}] " + spec.coverage_analysis,
        query=query,
        modules=modules,
        knowledge_ids=spec.knowledge_ids,
        positive=spec.positive,
        negative=spec.negative,
    ), {**provenance, "grammar": "grounded-detector-v7"}


def generate_grounded_spec(provider, context):
    operation = operation_for(context["requirement"])
    if context["strategy"] not in {"auto", "new_query"}:
        raise AuditError(
            "受限 detector 当前只支持 auto/new_query；其他策略需显式自由生成"
        )
    spec = provider.generate(
        "rule",
        {
            **context,
            "generation_mode": "grounded_detector_spec",
            "allowed_spec": {"language": context["language"], "operation": operation},
            "source_extension_scope": "Optional Python eval external module call return. Exact imported API call and external/untrusted business document must both be read and cited. Built-in framework sources use baseline. No file/line hardcoding or arbitrary QL.",
        },
        GroundedDetectorSpec,
    )
    return render_spec(spec, context)


def can_constrain(context, *, strict_scope=False):
    if context["purpose"] != "vulnerability_detector" or context["strategy"] not in {
        "auto",
        "new_query",
    }:
        return False
    if strict_scope and re.search(
        r"\bnosql\b|CWE-0?943(?!\d)|\b(?:dom|stored|persistent)\b|存储型|持久型",
        context["requirement"],
        re.I,
    ):
        # Relational SQL / reflected XSS templates must not masquerade as these.
        return False
    try:
        operation_for(context["requirement"])
    except AuditError:
        return False
    return True
