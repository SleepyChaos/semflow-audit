"""Bounded Flask routing model; inherits pinned HTTP and XSS semantics."""

import hashlib
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.adapters.codeql.rule_spec import detector_template
from app.contracts.stages import RuleResponse, StrictModel, TestFixture
from app.domain.audit import AuditError


class RouteShortcut(StrictModel):
    owner: Literal["Flask", "Blueprint"]
    method: Literal["get", "post"]
    evidence_id: UUID


class FlaskRouteSpec(StrictModel):
    language: Literal["python"]
    operation: Literal["xss"]
    purpose: Literal["vulnerability_detector"]
    title: str = Field(min_length=1, max_length=200)
    coverage_analysis: str = Field(min_length=10, max_length=2000)
    shortcuts: list[RouteShortcut] = Field(min_length=1, max_length=4)
    knowledge_ids: list[UUID] = Field(min_length=1, max_length=20)
    positive: TestFixture
    negative: TestFixture


def route_module(shortcuts):
    expressions = []
    for shortcut in shortcuts:
        owner = "FlaskApp" if shortcut.owner == "Flask" else "Blueprint"
        expressions.append(
            f'this = Flask::{owner}::instance().getMember("{shortcut.method}").getACall()'
        )
    return (
        """import python
import semmle.python.frameworks.Flask
import semmle.python.dataflow.new.DataFlow

class AdditionalFlaskRoute extends Flask::FlaskRouteSetup, DataFlow::CallCfgNode {
  AdditionalFlaskRoute() {
    """
        + "\n    or\n    ".join(dict.fromkeys(expressions))
        + """
  }
  override DataFlow::Node getUrlPatternArg() {
    result in [this.getArg(0), this.getArgByName("rule")]
  }
  override Function getARequestHandler() {
    result.getADecorator().getAFlowNode() = node
  }
}
"""
    )


def generate_flask_spec(provider, context):
    if (
        context["language"] != "python"
        or context["purpose"] != "vulnerability_detector"
    ):
        raise AuditError("Flask 路由模型目前仅支持 Python XSS detector")
    spec = provider.generate(
        "rule", {**context, "generation_mode": "flask_route_spec"}, FlaskRouteSpec
    )
    available = {row["id"]: row["content"] for row in context["knowledge"]}
    for shortcut in spec.shortcuts:
        symbol = f"flask.{shortcut.owner}.{shortcut.method}"
        if symbol not in available.get(str(shortcut.evidence_id), ""):
            raise AuditError("Flask 路由符号没有实际检索证据")
    query, provenance = detector_template("python", "xss")
    query = query.replace(
        "import python\n", "import python\nimport FlaskRouteModel\n", 1
    )
    module = route_module(spec.shortcuts)
    return RuleResponse(
        purpose=spec.purpose,
        title=spec.title,
        strategy="new_query",
        coverage_analysis="[model_extension] " + spec.coverage_analysis,
        query=query,
        modules={"FlaskRouteModel.qll": module},
        knowledge_ids=list(
            dict.fromkeys(
                [*spec.knowledge_ids, *[s.evidence_id for s in spec.shortcuts]]
            )
        ),
        positive=spec.positive,
        negative=spec.negative,
    ), {
        **provenance,
        "coverage": "model_extension",
        "grammar": "flask-route-shortcuts-v1",
        "module_sha256": hashlib.sha256(module.encode()).hexdigest(),
        "symbols": [f"flask.{s.owner}.{s.method}" for s in spec.shortcuts],
    }
