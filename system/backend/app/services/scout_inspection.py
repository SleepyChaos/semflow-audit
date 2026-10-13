"""V4 bounded security tasks, actual source pages and coverage-aware call allocation."""

import json

from app.contracts.discovery_semantics import FinalScoutResponseV6, ScoutResponseV6
from app.contracts.scouting import (
    FinalScoutResponseV4,
    FinalScoutResponseV5,
    ScoutResponseV4,
    ScoutResponseV5,
)
from app.domain.audit import AuditCancelled, AuditError
from app.persistence.stage_repository import StageCancelled
from app.services.context_materials import frozen_call, save_json
from app.services.read_tools import project_documents, window_observations
from app.services.review_tools import SOURCE_TOOL_CONTRACT, gather_review_tool


def compact_pages(rows):
    """Replace fully contained code pages by actual larger pages, without truncation."""
    unique = list({r["id"]: r for r in rows}.values())
    result = []
    for row in unique:
        ref = row["reference"]
        covered = row["kind"] == "code" and any(
            other["kind"] == "code"
            and other["id"] != row["id"]
            and other["reference"].get("file") == ref.get("file")
            and other["reference"]["start_line"] <= ref["start_line"]
            and other["reference"]["end_line"] >= ref["end_line"]
            and (
                other["reference"]["start_line"] < ref["start_line"]
                or other["reference"]["end_line"] > ref["end_line"]
            )
            for other in unique
        )
        if not covered:
            result.append(row)
    return result


def eligible_units(service, project):
    units = project["units"]
    if service.inputs.inspection_paths:
        roots = [service.evidence.allowed(p) for p in service.inputs.inspection_paths]
        units = [
            u
            for u in units
            if any(
                service.evidence.allowed(u["file"]).is_relative_to(root)
                for root in roots
            )
        ]
    if not service.inputs.include_third_party:
        units = [u for u in units if u["role_hint"] != "third_party_or_generated"]
    return units


def selected_units(service, project):
    units = eligible_units(service, project)
    if service.inputs.continuation_from_id:
        done = set(
            service.stage.result.get("continuation", {}).get("inherited_unit_ids", [])
        )
        units = [unit for unit in units if unit["id"] not in done]
    return units[: service.inputs.max_units] if service.inputs.max_units else units


def call_allocation(service, remaining_units):
    maximum = getattr(service.provider, "policy", {}).get("max_calls", 24)
    if maximum == 0:
        return service.inputs.steps_per_unit
    available = maximum - service.provider.usage.get("calls", 0)
    return max(
        1, min(service.inputs.steps_per_unit, available - max(0, remaining_units - 1))
    )


def validate_checks(response, context, semantic=False):
    required = {t["id"] for t in context["inspection_tasks"]}
    actual = [t.task_id for t in response.task_checks]
    if len(actual) != len(set(actual)) or set(actual) != required:
        raise AuditError("每个已分配安全任务必须有且仅有一条检查记录；未知也需记录")
    ids = {r["id"] for r in context["evidence"]}
    for check in response.task_checks:
        if not set(map(str, check.evidence_ids)) <= ids:
            raise AuditError("检查记录引用了未读取的证据")
        if check.status != "unknown" and not check.evidence_ids:
            raise AuditError("已调查或不适用判断需要本轮实际证据")
        if semantic and check.status != "unknown":
            from app.adapters.source_inventory import inspectable

            if not any(
                r["id"] in set(map(str, check.evidence_ids))
                and r["kind"] == "code"
                and inspectable(r["reference"].get("file", ""), context["language"])
                for r in context["evidence"]
            ):
                raise AuditError("任务调查需要实际项目源码，不能只引用文档")


def inspect_unit(service, project, unit, call_limit):
    from app.adapters.project_map import map_context
    from app.adapters.python_bindings import window_bindings

    source = service.evidence.read(unit["file"], unit["start_line"], unit["end_line"])
    context = {
        "snapshot": project["snapshot"],
        "language": project["language"],
        "unit": unit,
        "project_map": map_context(project, unit),
        "evidence": [source, *project_documents(service.evidence)],
        "tool_trace": [],
        "scope": service.inputs.paths,
        "anchors": [],
        "stage": "independent_security_task_investigation",
        "inspection_tasks": unit["inspection_tasks"],
        "tool_contract": SOURCE_TOOL_CONTRACT,
        "symbol_bindings": window_bindings(service.evidence, source["reference"]),
        "assessment_boundary": "Source-level conditions. External deployment assumptions are separate unknowns, not invented guards. Task completion does not prove a module safe.",
    }
    # A small complete module can supply control/return context without another LLM call.
    path = service.evidence.allowed(unit["file"])
    lines = path.read_text().splitlines()
    if path.stat().st_size <= 10000 and len(lines) <= 300:
        for start in range(1, len(lines) + 1, 150):
            end = min(start + 149, len(lines))
            if len("\n".join(lines[start - 1 : end])) <= 6000:
                page = service.evidence.read(unit["file"], start, end)
                proposed = compact_pages([*context["evidence"], page])
                if (
                    len(
                        json.dumps(
                            {**context, "evidence": proposed}, ensure_ascii=False
                        )
                    )
                    <= service.inputs.max_context_chars - 4000
                ):
                    context["evidence"] = list({r["id"]: r for r in proposed}.values())
    if service.stage.prompt_version in {"6", "7", "8"}:
        from app.services.discovery_context import augment_context

        context = augment_context(service, context)
        from app.adapters.route_inventory import route_inventory

        context["route_inventory"] = route_inventory(
            service.evidence, unit["file"], unit["start_line"], unit["end_line"]
        )
        context["route_obligation"] = (
            "Return one route_check for every listed route_id. A missing_authentication check needs its own authentication finding for THIS endpoint; never bundle another endpoint into its description. Public login/register routes may be public_expected; infer sensitivity from actual business code, not names alone."
        )
    fallback = None
    localization_attempted = False
    for step in range(call_limit):
        service.active()
        context["source_windows"] = window_observations(
            service.evidence, context["evidence"]
        )
        context["remaining_model_calls_in_unit"] = call_limit - step
        final_only = (
            fallback is not None
            or step == call_limit - 1
            or any(r.get("reused") for r in context["tool_trace"])
        )
        context["finalize_required"] = final_only
        from app.adapters.context_packing import fit_navigation

        context = fit_navigation(context, service.inputs.max_context_chars)
        if (
            len(json.dumps(context, ensure_ascii=False))
            > service.inputs.max_context_chars
        ):
            if fallback is not None:
                save_json(
                    service.directory
                    / "units"
                    / unit["id"]
                    / "localization-recovery-error.json",
                    {
                        "code": "context_budget",
                        "reason": "Localization feedback cannot fit; original valid findings retained, rejected proposals remain unknown.",
                    },
                )
                return fallback
            raise AuditError(
                "粗筛必要上下文超过预算；未截断证据", code="context_budget"
            )
        directory = service.directory / "units" / unit["id"]
        try:
            response = frozen_call(
                service.provider,
                "scout",
                context,
                (FinalScoutResponseV6 if final_only else ScoutResponseV6)
                if service.stage.prompt_version in {"6", "7", "8"}
                else (FinalScoutResponseV5 if final_only else ScoutResponseV5)
                if service.stage.prompt_version == "5"
                else (FinalScoutResponseV4 if final_only else ScoutResponseV4),
                directory / f"call-{step}",
                limit=getattr(service.provider, "policy", {}).get("max_calls", 24),
                ledger_directory=service.directory,
            )
        except StageCancelled, AuditCancelled:
            raise
        except AuditError as exc:
            if fallback is None or exc.code in {"integrity_error", "identity_error"}:
                raise
            save_json(
                directory / "localization-recovery-error.json",
                {"code": exc.code, "reason": str(exc)},
            )
            return fallback
        service.active()
        if response.action == "final":
            try:
                if service.stage.prompt_version not in {"6", "7", "8"}:
                    validate_checks(response, context)
                accepted, rejected = [], []
                for row in response.findings:
                    if service.stage.prompt_version not in {"6", "7", "8"}:
                        service.hypothesis(row, context)
                        continue
                    try:
                        service.hypothesis(row, context)
                        if (
                            row.primary_location.file != unit["file"]
                            or not unit["start_line"]
                            <= row.primary_location.line
                            <= unit["end_line"]
                        ):
                            raise AuditError(
                                "Candidate operation belongs to another scheduled source window"
                            )
                    except AuditError as exc:
                        if exc.code in {"integrity_error", "identity_error"}:
                            raise
                        rejected.append(
                            {
                                "hypothesis": row.model_dump(mode="json"),
                                "reason": str(exc),
                                "code": exc.code,
                            }
                        )
                    else:
                        accepted.append(row)
                if service.stage.prompt_version in {"6", "7", "8"}:
                    from app.services.scout_localization import merge_findings

                    response.findings = merge_findings(
                        fallback.findings if fallback else [], accepted
                    )
                    from app.services.route_obligations import reconcile_receipts

                    receipt_rejections = reconcile_receipts(response, context)
                    save_json(directory / "rejected-receipts.json", receipt_rejections)
                    save_json(
                        directory / f"validation-attempt-{step}.json",
                        {
                            "rejected_hypotheses": rejected,
                            "rejected_receipts": receipt_rejections,
                        },
                    )
                    save_json(directory / "rejected-hypotheses.json", rejected)
                    from app.services.scout_localization import localization_feedback

                    feedback = localization_feedback(rejected, context)
                    if (
                        feedback
                        and not localization_attempted
                        and step + 1 < call_limit
                    ):
                        fallback = response
                        localization_attempted = True
                        context["server_feedback"] = feedback
                        continue
            except AuditError as exc:
                if exc.code in {"identity_error", "integrity_error"}:
                    raise
                context["server_feedback"] = str(exc)
                continue
            save_json(directory / "evidence-coverage.json", context["source_windows"])
            return response
        if response.tool.name not in {"read_source", "search_source", "callers"}:
            raise AuditError("粗筛只允许源码工具")
        previous = context
        try:
            proposed = gather_review_tool(service, context, response.tool.model_dump())
        except StageCancelled, AuditCancelled:
            raise
        except AuditError as exc:
            if exc.code in {
                "integrity_error",
                "identity_error",
                "budget_exhausted",
            }:
                raise
            # Refusal is not a read, and must not erase an already inspected unit.
            context = {
                **previous,
                "latest_tool_observation": {
                    "status": "context_budget"
                    if exc.code == "context_budget"
                    else "source_unavailable_or_forbidden",
                    "reason": str(exc),
                    "requested": response.tool.model_dump(),
                    "meaning": "No requested body was provided. Use supplied inventory and legal pages. Credentials/scope violations remain blocked; record the missing premise if access is impossible.",
                },
            }
            continue
        proposed["evidence"] = compact_pages(proposed["evidence"])
        if (
            len(json.dumps(proposed, ensure_ascii=False))
            <= service.inputs.max_context_chars - 2000
        ):
            context = proposed
        else:
            context = {
                **previous,
                "server_feedback": "The tool read was stored but its new body cannot fit this context. It is NOT supplied evidence: do not cite its ID. Request a narrower new page or finalize with a precise missing premise. Existing evidence is preserved.",
            }
    if fallback is not None:
        return fallback
    raise AuditError("任务检查或取证步数耗尽，保留未完成状态", code="unit_budget")


def task_coverage(result, project):
    records = {r["unit_id"]: r for r in result.get("units", [])}
    matrix = []
    for unit in project["units"]:
        checks = {
            r["task_id"]: r for r in records.get(unit["id"], {}).get("task_checks", [])
        }
        matrix.append(
            {
                "unit_id": unit["id"],
                "file": unit["file"],
                "start_line": unit["start_line"],
                "end_line": unit["end_line"],
                "role_hint": unit["role_hint"],
                "tasks": [
                    {
                        "task_id": t["id"],
                        "status": checks.get(t["id"], {}).get("status", "uninspected"),
                    }
                    for t in unit["inspection_tasks"]
                ],
            }
        )
    return {
        "matrix": matrix,
        "status_counts": {
            name: sum(t["status"] == name for r in matrix for t in r["tasks"])
            for name in ("investigated", "unknown", "not_applicable", "uninspected")
        },
        "meaning": "Model investigation receipts, not verified safety or exhaustive business-flow coverage",
    }
