"""Check endpoint investigation receipts against the supplied source and hypotheses."""

from app.domain.audit import AuditError
from app.services.read_tools import grounded


def validate_routes(response, context):
    required = {r["route_id"]: r for r in context["route_inventory"]["routes"]}
    actual = [r.route_id for r in response.route_checks]
    if len(actual) != len(set(actual)) or set(actual) != set(required):
        raise AuditError("每个语法端点都需要独立的认证调查记录，未知也需记录")
    materials = {r["id"]: r for r in context["evidence"]}
    for check in response.route_checks:
        route = required[check.route_id]
        ids = set(map(str, check.evidence_ids))
        if not ids <= materials.keys():
            raise AuditError("端点检查引用了未提供证据")
        if check.authentication != "unknown" and not grounded(
            [materials[i] for i in ids],
            {"file": route["file"], "line": route["start_line"]},
        ):
            raise AuditError("端点判断需要真实注册位置源码；解析清单不是源码引用")
        if check.authentication == "missing_authentication" and not any(
            f.security_property == "authentication"
            and (f.route_id == route["route_id"] or f.endpoint == route["endpoint"])
            and f.primary_location.file == route["file"]
            and route["start_line"] <= f.primary_location.line <= route["end_line"]
            for f in response.findings
        ):
            raise AuditError(
                f"缺认证端点 {route['endpoint']}（route_id={route['route_id']}，行 {route['start_line']}-{route['end_line']}）需要其独立候选及匹配route_id，不能捆绑成其他端点的次要描述"
            )


def validate_task_conclusions(response):
    for check in response.task_checks:
        if check.status == "unknown" and check.conclusion != "unknown":
            raise AuditError("未决任务不能输出已调查安全结论")
        if check.status == "not_applicable" and check.conclusion != "not_applicable":
            raise AuditError("不适用任务须明确登记不适用结论")
        if check.status == "investigated":
            if check.conclusion not in {"suspicious", "no_condition_identified"}:
                raise AuditError(
                    "已调查任务须分别登记发现可疑条件或未发现条件；不能以泛化调查记录漏掉发现"
                )
            if check.conclusion == "suspicious" and not any(
                f.security_property == check.task_id for f in response.findings
            ):
                raise AuditError(
                    f"任务 {check.task_id} 有可疑条件，但没有对应独立候选；需输出假设或保留未决"
                )


def reconcile_receipts(response, context):
    """Quarantine invalid receipts independently; never turn missing work into safety."""
    from types import SimpleNamespace

    from app.contracts.discovery_semantics import RouteCheck, SemanticTaskCheck
    from app.services.scout_inspection import validate_checks

    rejected = []
    tasks = []
    for task in context["inspection_tasks"]:
        matches = [c for c in response.task_checks if c.task_id == task["id"]]
        try:
            if len(matches) != 1:
                raise AuditError("Missing or duplicate task receipt")
            check = matches[0]
            single = SimpleNamespace(task_checks=[check], findings=response.findings)
            validate_checks(
                single, {**context, "inspection_tasks": [task]}, semantic=True
            )
            validate_task_conclusions(single)
        except AuditError as exc:
            rejected.append(
                {
                    "kind": "task",
                    "id": task["id"],
                    "reason": str(exc),
                    "original": [c.model_dump(mode="json") for c in matches],
                }
            )
            check = SemanticTaskCheck(
                task_id=task["id"],
                status="unknown",
                conclusion="unknown",
                reason=("Host validation: " + str(exc))[:240],
            )
        tasks.append(check)
    routes = []
    for route in context["route_inventory"]["routes"]:
        matches = [c for c in response.route_checks if c.route_id == route["route_id"]]
        try:
            if len(matches) != 1:
                raise AuditError("Missing or duplicate route receipt")
            check = matches[0]
            validate_routes(
                SimpleNamespace(route_checks=[check], findings=response.findings),
                {**context, "route_inventory": {"routes": [route]}},
            )
        except AuditError as exc:
            rejected.append(
                {
                    "kind": "route",
                    "id": route["route_id"],
                    "reason": str(exc),
                    "original": [c.model_dump(mode="json") for c in matches],
                }
            )
            check = RouteCheck(
                route_id=route["route_id"],
                authentication="unknown",
                reason=("Host validation: " + str(exc))[:240],
            )
        routes.append(check)
    for kind, rows, attr, valid in (
        (
            "task",
            response.task_checks,
            "task_id",
            {t["id"] for t in context["inspection_tasks"]},
        ),
        (
            "route",
            response.route_checks,
            "route_id",
            {r["route_id"] for r in context["route_inventory"]["routes"]},
        ),
    ):
        for check in rows:
            if getattr(check, attr) not in valid:
                rejected.append(
                    {
                        "kind": kind,
                        "reason": "Unassigned receipt",
                        "original": check.model_dump(mode="json"),
                    }
                )
    response.task_checks, response.route_checks = tasks, routes
    return rejected
