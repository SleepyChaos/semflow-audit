"""Algorithm extracted from app.services.scouting.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Bounded independent discovery with explicit source coverage and immutable attempts."""
import json
from datetime import UTC

from semflow_contracts.modelio.scouting import ScoutRequest, ScoutResponse

from semflow_research.adapters.artifacts import ArtifactStore
from semflow_research.adapters.project_map import build_project_map, map_context
from semflow_research.domain.errors import (
    AuditCancelled,
    AuditError,
    ExecutionCancelled,
)
from semflow_research.evidence.context_materials import (
    digest,
    frozen_call,
    save_json,
    verify_snapshot,
)
from semflow_research.evidence.evidence import EvidenceService
from semflow_research.evidence.read_tools import (
    grounded,
    observe_tool,
    project_documents,
    reused_read,
    source_tool,
    window_observations,
)
from semflow_research.state.models import Candidate, ExecutionRecord


class ScoutService:
    def __init__(self, execution_id, provider, *, _kernel):
        self._kernel = _kernel
        self.execution_id, self.provider = (str(execution_id), provider)
        self.repository = _kernel.execution_records
        self.execution = self.repository.get(self.execution_id)
        self.inputs = ScoutRequest.model_validate(self.execution.inputs)
        from semflow_research.discovery.specification_guidance import prepare_guidance

        self.guidance = prepare_guidance(_kernel)
        self.directory = ArtifactStore(_kernel=_kernel).directory(self.execution_id)
        self.evidence = EvidenceService(
            str(self.execution.snapshot_id),
            self.execution_id,
            self.inputs.paths,
            _kernel=_kernel,
        )

    def active(self):
        _kernel = self._kernel
        self.repository.active(self.execution_id)
        if (
            _kernel.source_records.get(str(self.execution.snapshot_id)).status
            == "cancelled"
        ):
            raise AuditCancelled("审计已取消，停止独立粗筛")

    def prepare(self, _):
        _kernel = self._kernel
        self.active()
        for path in self.inputs.inspection_paths:
            self.evidence.allowed(path)
        path = self.directory / "scout-map.json"
        if path.exists():
            project = json.loads(path.read_text())
            if project["snapshot"] != self.evidence.source_context.snapshot_hash:
                raise AuditError("项目地图快照不匹配")
        else:
            if self.inputs.continuation_from_id:
                from semflow_research.discovery.scout_continuation import frozen_map

                previous = self.repository.get(str(self.inputs.continuation_from_id))
                if (
                    previous.snapshot_id != self.execution.snapshot_id
                    or previous.kind != "scout"
                ):
                    raise AuditError("补审来源不属于当前审计")
                project = frozen_map(
                    previous, self.evidence.source_context, _kernel=_kernel
                )
            else:
                project = build_project_map(
                    self.evidence,
                    self.inputs.window_lines,
                    "business_semantic"
                    if self.execution.method_version in {"6", "7", "8"}
                    else "business_first"
                    if self.execution.method_version in {"4", "5", "6", "7", "8"}
                    else "balanced",
                    scheduling_profile=self.inputs.scheduling_profile,
                )
            save_json(path, project)
        identity = digest({"project": project, "inputs": self.execution.inputs})
        receipt = self.directory / "scout-map-receipt.json"
        if receipt.exists() and json.loads(receipt.read_text())["identity"] != identity:
            raise AuditError("粗筛地图或范围被修改")
        save_json(receipt, {"identity": identity})
        self.repository.update(
            self.execution_id, phase="scout_windows", model=self.provider.model
        )
        return {"map_hash": identity}

    def hypothesis(self, row, context):
        from semflow_research.adapters.source_inventory import inspectable

        if self.execution.method_version in {"6", "7", "8"}:
            from semflow_research.adapters.operation_evidence import locate_quote

            locate_quote(row, context, self.evidence.source_context.language)
        if not inspectable(
            row.primary_location.file, self.evidence.source_context.language
        ):
            raise AuditError("粗筛候选必须位于项目源码，文档不能作为主位置")
        rows = [
            r for r in context["evidence"] if r["id"] in set(map(str, row.evidence_ids))
        ]
        if len(rows) != len(set(row.evidence_ids)) or not grounded(
            rows, row.primary_location.model_dump()
        ):
            raise AuditError("粗筛候选位置必须关联实际已读源码")
        self.evidence.allowed(row.primary_location.file)
        if self.execution.method_version in {"2", "3", "4", "5", "6", "7", "8"}:
            from semflow_research.adapters.python_bindings import location_bindings

            for clue in location_bindings(
                self.evidence, [row.primary_location.model_dump()]
            ):
                unresolved = [
                    c["name"]
                    for c in clue.get("direct_calls", [])
                    if c["binding"] in {"no_static_binding", "unknown_dynamic_scope"}
                ]
                if unresolved:
                    premise = (
                        "Verify actual API binding; unresolved names: "
                        + ", ".join(unresolved)
                    )
                    row.missing_premises = list(
                        dict.fromkeys([*row.missing_premises[:9], premise])
                    )

    def inspect_unit(self, project, unit):
        _kernel = self._kernel
        source = self.evidence.read(unit["file"], unit["start_line"], unit["end_line"])
        context = {
            "snapshot": project["snapshot"],
            "language": project["language"],
            "unit": unit,
            "project_map": map_context(project, unit),
            "evidence": [source, *project_documents(self.evidence)],
            "tool_trace": [],
            "scope": self.inputs.paths,
            "stage": "independent_source_hypotheses",
        }
        context["source_windows"] = window_observations(
            self.evidence, context["evidence"]
        )
        modern = self.execution.method_version in {"2", "3", "4", "5", "6", "7", "8"}
        if modern:
            from semflow_research.adapters.python_bindings import window_bindings
            from semflow_research.discovery.review_tools import SOURCE_TOOL_CONTRACT

            context.update(
                tool_contract=SOURCE_TOOL_CONTRACT,
                anchors=[],
                symbol_bindings=window_bindings(self.evidence, source["reference"]),
            )
        for step in range(self.inputs.steps_per_unit):
            self.active()
            if (
                len(json.dumps(context, ensure_ascii=False))
                > self.inputs.max_context_chars
            ):
                raise AuditError("粗筛关键上下文超过预算", code="context_budget")
            response = frozen_call(
                self.provider,
                "scout",
                context,
                ScoutResponse,
                self.directory / "units" / unit["id"] / f"call-{step}",
                limit=getattr(self.provider, "policy", {}).get("max_calls", 24),
                ledger_directory=self.directory,
                _kernel=_kernel,
            )
            self.active()
            if response.action == "final":
                for row in response.findings:
                    self.hypothesis(row, context)
                return response
            call = response.tool.model_dump()
            if modern:
                from semflow_research.discovery.review_tools import gather_review_tool

                if call["name"] not in {"read_source", "search_source", "callers"}:
                    raise AuditError("粗筛只允许源码读取、搜索和调用线索工具")
                context = gather_review_tool(self, context, call, _kernel=_kernel)
                continue
            previous = reused_read(context, call)
            data = previous or source_tool(self.evidence, call)
            if data["id"] not in {r["id"] for r in context["evidence"]}:
                context["evidence"].append(data)
            context = observe_tool(context, call, data, reused=previous is not None)
            context["source_windows"] = window_observations(
                self.evidence, context["evidence"]
            )
        raise AuditError("该窗口取证步数耗尽，保留未完成状态", code="unit_budget")

    def save_unit(self, unit, response):
        _kernel = self._kernel
        self.active()
        from semflow_research.discovery.specification_guidance import guidance_receipt

        metadata = []
        guidance = guidance_receipt(self, unit)
        with _kernel.records.transaction() as db:
            stage = db.one(ExecutionRecord, id=self.execution.id)
            if stage.status == "cancelled":
                raise ExecutionCancelled("粗筛已取消")
            rejected = []
            for row in response.findings:
                if stage.method_version in {"3", "4", "5", "6", "7", "8"}:
                    from semflow_research.adapters.python_bindings import (
                        unbound_operation,
                    )

                    if unbound_operation(
                        self.evidence, row.primary_location.model_dump(), row.weakness
                    ):
                        rejected.append(
                            {
                                "hypothesis": row.model_dump(mode="json"),
                                "reason": "No static API binding: retained as raw observation, not an executable injection candidate",
                            }
                        )
                        continue
                logical = row.model_dump(mode="json")
                logical.pop("evidence_ids")
                if self.execution.method_version in {"6", "7", "8"}:
                    from semflow_research.adapters.route_inventory import (
                        condition_identity,
                    )

                    logical = condition_identity(self.evidence, row)
                identity = "scout:" + digest(
                    {
                        "snapshot": self.evidence.source_context.snapshot_hash,
                        "hypothesis": logical,
                    }
                )
                candidate = db.first(
                    Candidate, execution_id=stage.id, identity_key=identity
                )
                if candidate is None:
                    candidate = Candidate(
                        snapshot_id=stage.snapshot_id,
                        execution_id=stage.id,
                        origin="ai",
                        title=row.title,
                        description=row.observation,
                        weakness=row.weakness,
                        model_assessment="pending",
                        novelty="unverified",
                        identity_key=identity,
                        location=row.primary_location.model_dump(),
                        related_target=unit["id"],
                        evidence_ids=list(map(str, row.evidence_ids)),
                    )
                    db.save(candidate)
                metadata.append(
                    {
                        "candidate_id": str(candidate.id),
                        **row.model_dump(mode="json"),
                        **(
                            {
                                "discovery_mode": "specification_guided",
                                "security_specifications": guidance["supplied"],
                            }
                            if guidance.get("supplied")
                            else {}
                        ),
                    }
                )
            result = dict(stage.result)
            results = {r["unit_id"]: r for r in result.get("units", [])}
            saved = {
                "unit_id": unit["id"],
                "status": "inspected",
                "scope_summary": response.scope_summary,
                "hypotheses": metadata,
                "binding_unresolved_observations": rejected,
                **({"specification_lookup": guidance} if guidance else {}),
                "route_checks": [
                    r.model_dump(mode="json")
                    for r in getattr(response, "route_checks", [])
                ],
                "task_checks": [
                    r.model_dump(mode="json")
                    for r in getattr(response, "task_checks", [])
                ],
            }
            results[unit["id"]] = saved
            stage.result = {**result, "units": list(results.values())}
            db.save(stage)
            db.commit()
        save_json(self.directory / "units" / unit["id"] / "result.json", saved)

    def inspect(self, state):
        _kernel = self._kernel
        project = json.loads((self.directory / "scout-map.json").read_text())
        if (
            digest({"project": project, "inputs": self.execution.inputs})
            != state["map_hash"]
        ):
            raise AuditError("粗筛地图已变化")
        self.active()
        stopped = None
        from semflow_research.discovery.scout_inspection import (
            call_allocation,
            inspect_unit,
            selected_units,
        )

        modern = self.execution.method_version in {"4", "5", "6", "7", "8"}
        units = (
            selected_units(self, project)
            if modern
            else project["units"][: self.inputs.max_units]
            if self.inputs.max_units
            else project["units"]
        )
        for index, unit in enumerate(units):
            current = self.repository.get(self.execution_id).result
            from datetime import datetime

            progress_path = self.directory / "scout-progress.json"
            save_json(
                progress_path,
                {
                    "status": "running",
                    "observed_at": datetime.now(UTC).isoformat(),
                    "unit_id": unit["id"],
                    "file": unit["file"],
                    "scheduled_windows": len(units),
                    "completed_windows": len(
                        {
                            r["unit_id"]
                            for r in current.get("units", [])
                            if r["status"] == "inspected"
                        }
                    ),
                    "calls": self.provider.usage.get("calls", 0),
                    "meaning": "Actual completed-window and call counters; process heartbeat alone is not progress",
                },
            )
            if unit["id"] in {
                r["unit_id"]
                for r in current.get("units", [])
                if r["status"] == "inspected"
            }:
                continue
            try:
                response = (
                    inspect_unit(
                        self,
                        project,
                        unit,
                        call_allocation(self, len(units) - index),
                        _kernel=_kernel,
                    )
                    if modern
                    else self.inspect_unit(project, unit)
                )
                self.save_unit(unit, response)
            except (ExecutionCancelled, AuditCancelled):
                raise
            except Exception as exc:
                code = getattr(exc, "code", "inspection_failed")
                if code in {"integrity_error", "identity_error"}:
                    raise
                failed = {
                    "unit_id": unit["id"],
                    "status": "incomplete",
                    "reason": str(exc)[:500],
                    "code": code,
                }
                from semflow_research.discovery.specification_guidance import (
                    guidance_receipt,
                )

                guidance = guidance_receipt(self, unit)
                if guidance:
                    failed["specification_lookup"] = guidance
                current = self.repository.get(self.execution_id).result
                self.repository.update(
                    self.execution_id,
                    result={**current, "units": [*current.get("units", []), failed]},
                )
                if code in {
                    "budget_exhausted",
                    "timeout",
                    "provider_error",
                    "rate_limited",
                }:
                    stopped = code
                    break
                from semflow_research.adapters.ai.policy import stalled

                if stalled(
                    self.repository.get(self.execution_id).result.get("units", []),
                    getattr(self.provider, "policy", {}),
                ):
                    stopped = "no_progress"
                    break
        return {"stop_reason": stopped}

    def finalize(self, state):
        self.active()
        verify_snapshot(self.evidence)
        project = json.loads((self.directory / "scout-map.json").read_text())
        result = self.repository.get(self.execution_id).result
        done = {
            r["unit_id"] for r in result.get("units", []) if r["status"] == "inspected"
        }
        files = []
        for row in project["files"]:
            units = [u for u in project["units"] if u["file"] == row["file"]]
            files.append(
                {
                    "file": row["file"],
                    "module": row["module"],
                    "total_windows": len(units),
                    "inspected_windows": sum(u["id"] in done for u in units),
                }
            )
        gaps = len(done) != len(project["units"]) or bool(project["skipped"])
        coverage = {
            "status": "partial" if gaps else "completed",
            "planned_windows": len(project["units"]),
            "inspected_windows": len(done),
            "uninspected_windows": len(project["units"]) - len(done),
            "files": files,
            "skipped": project["skipped"],
            "stop_reason": state.get("stop_reason"),
            "map_artifact": "scout-map.json",
            "meaning": "Inspected windows are not verified safe business flows",
        }
        if self.execution.method_version in {"4", "5", "6", "7", "8"}:
            from semflow_research.discovery.scout_inspection import (
                eligible_units,
                selected_units,
                task_coverage,
            )

            selected = done | {u["id"] for u in selected_units(self, project)}
            eligible = {
                u["id"]
                for u in project["units"]
                if self.inputs.include_third_party
                or u["role_hint"] != "third_party_or_generated"
            }
            coverage.update(
                continuable_windows=sum(
                    u["id"] not in done for u in eligible_units(self, project)
                ),
                eligible_windows=len(eligible),
                inspected_eligible_windows=len(done & eligible),
                scheduled_windows=len(selected),
                deferred_windows=[
                    {
                        **u,
                        "reason": "third_party_deferred"
                        if u["id"] not in eligible
                        else "max_units_limit",
                    }
                    for u in project["units"]
                    if u["id"] not in selected
                ],
                business_coverage_status="completed" if eligible <= done else "partial",
                task_coverage=task_coverage(result, project),
            )
        result = {**result, "coverage": coverage, "snapshot_hash": project["snapshot"]}
        save_json(
            self.directory / "scout-progress.json",
            {
                "status": "stage_finished",
                "coverage_status": coverage["status"],
                "completed_windows": len(done),
                "planned_windows": len(project["units"]),
                "calls": self.provider.usage.get("calls", 0),
            },
        )
        save_json(self.directory / "scout-result.json", result)
        self.repository.update(
            self.execution_id,
            status="completed",
            phase="hypotheses_ready",
            result=result,
            usage=self.provider.usage,
        )
        return {"saved": True}
