"""Algorithm extracted from app.services.repair_semantics.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Semantic repair: fixed source, evidence contract and bounded complete candidates."""
import json
import shutil

from semflow_contracts.modelio.repair_semantics import FailureDiagnosis
from semflow_contracts.modelio.stages import RepairResponse

from semflow_research.adapters.repair.patches import apply_changes
from semflow_research.domain.errors import AuditError
from semflow_research.evidence.context_materials import (
    candidate_materials,
    digest,
    frozen_call,
    save_json,
    semantic_policy,
    verify_snapshot,
)
from semflow_research.evidence.semantic_inspection import SemanticInspection
from semflow_research.state.models import Candidate, RepairRecord


class SemanticRepair:
    def __init__(self, service, *, _kernel):
        self._kernel = _kernel
        self.service = service
        self.directory = service.directory
        self.policy = semantic_policy(self.directory, _kernel=_kernel)
        self.reader = SemanticInspection(
            service.evidence,
            service.provider,
            self.directory,
            service.repository,
            "repair",
            progressive=True,
            require_grounded_source=True,
            _kernel=_kernel,
        )

    def targets(self):
        _kernel = self._kernel
        s = self.service
        with _kernel.records.transaction() as db:
            targets = db.list(
                Candidate,
                snapshot_id=s.execution.snapshot_id,
                id__in=s.inputs.candidate_ids,
            )
        if len(targets) != len(set(s.inputs.candidate_ids)) or any(
            t.status != "confirmed" for t in targets
        ):
            raise AuditError("修复目标确认状态变化或不属于本审计")
        verify_snapshot(s.evidence)
        return targets

    def prepare(self, _):
        _kernel = self._kernel
        s = self.service
        targets = self.targets()
        from semflow_research.adapters.repair.readiness import require_targets

        preliminary = s.inputs.allowed_paths or sorted(
            {t.location["file"] for t in targets if t.location.get("file")}
        )
        require_targets(s.evidence.root, preliminary)
        materials = candidate_materials(s.evidence, targets, _kernel=_kernel)
        from semflow_research.repair.repair_inputs import (
            ensure_target_bodies,
            patch_context,
            select_paths,
        )

        paths = select_paths(s.inputs, targets, materials)
        materials = ensure_target_bodies(s.evidence, targets, materials, paths)
        descriptions = [
            {
                "id": str(t.id),
                "title": t.title,
                "description": t.description,
                "weakness": t.weakness,
                "location": t.location,
            }
            for t in targets
        ]
        from semflow_research.repair.repair_requirements import (
            acceptance_contract,
            request_materials,
        )

        acceptance = acceptance_contract(s, _kernel=_kernel)
        image_id = None
        if (
            acceptance
            and s.execution.method_version in {"3", "4"}
            and _kernel.spec.inputs.method_policy.selected_suite_feedback
        ):
            from semflow_research.adapters.repair.verification_runner import (
                resolve_image,
            )

            image_id = resolve_image(acceptance["image"])
        materials = [
            *materials,
            *request_materials(s.evidence, descriptions, acceptance),
        ]
        inspection = self.reader.inspect(
            descriptions,
            materials,
            requested_behavior=acceptance,
            repair_scope={
                "writable_files": paths,
                "meaning": "Only these files are authorized patch targets. Other source is read-only context; inspect it only to establish dependencies or callers of these targets, not to expand this repair to another subsystem.",
            },
        )
        contents, views = patch_context(s.evidence, paths, inspection["evidence"])
        bundle = {
            "targets": descriptions,
            "target_identities": {
                str(t.id): digest(t.model_dump(mode="json")) for t in targets
            },
            "allowed_files": contents,
            "file_views": views,
            "patch_contract": "allowed_files may contain exact windows, not complete files; only replace text in a supplied segment; omitted text is unknown; preserve the original snapshot and all other content",
            "materials": materials,
            "inspection": inspection,
            "acceptance_contract": acceptance,
            "verification_image_id": image_id,
            "candidate_suite_feedback": bool(image_id),
            "snapshot": s.evidence.source_context.snapshot_hash,
            "validation_profile": s.inputs.validation_profile,
            "validation_limit": "Existing syntax/project tests and optional static rescan only; no new exploit oracle",
        }
        save_json(self.directory / "repair-context.json", bundle)
        s.repository.update(
            s.execution_id,
            phase="semantic_context_ready",
            model=s.provider.model,
            result={"semantic_artifact": "repair-context.json", "allowed_paths": paths},
        )
        return {"context_hash": digest(bundle), "attempt": 0, "allowed_paths": paths}

    def context(self, state, *, proposing=False):
        _kernel = self._kernel
        bundle = json.loads((self.directory / "repair-context.json").read_text())
        if digest(bundle) != state["context_hash"]:
            raise AuditError("修复语义上下文被修改")
        from semflow_research.repair.repair_requirements import acceptance_contract

        current_acceptance = acceptance_contract(self.service, _kernel=_kernel)
        frozen_acceptance = bundle.get("acceptance_contract")
        if (
            frozen_acceptance is not None
            and "image" not in frozen_acceptance
            and isinstance(current_acceptance, dict)
        ):
            current_acceptance = {
                key: value
                for key, value in current_acceptance.items()
                if key != "image"
            }
        if frozen_acceptance != current_acceptance:
            raise AuditError("所选验收要求在修复期间发生变化")
        targets = self.targets()
        if bundle["target_identities"] != {
            str(t.id): digest(t.model_dump(mode="json")) for t in targets
        }:
            raise AuditError("修复目标内容已变化")
        payload = {**bundle, "phase": "propose_patch"}
        payload["file_views"] = {
            name: {
                **view,
                "segments": [
                    {k: v for k, v in row.items() if k != "content"}
                    for row in view["segments"]
                ],
            }
            for name, view in bundle["file_views"].items()
        }
        inspection = dict(bundle["inspection"])
        inspection["evidence"] = [
            {
                **row,
                "content": "See exact allowed_files content; original evidence stored in context artifact",
            }
            if row["kind"] == "code"
            and bundle["file_views"]
            .get(row["reference"].get("file"), {})
            .get("complete")
            else row
            for row in inspection["evidence"]
        ]
        payload["inspection"] = inspection
        payload.pop("materials")
        if state.get("attempt"):
            feedback_identity = (state.get("diagnosis") or {}).get("candidate_identity")
            if feedback_identity and (
                feedback_identity["execution_id"] != str(self.service.execution_id)
                or feedback_identity["snapshot_id"]
                != str(self.service.execution.snapshot_id)
                or (
                    proposing
                    and (
                        feedback_identity["attempt"] != state["attempt"]
                        or feedback_identity.get("proposal_hash")
                        != state.get("proposal_hash")
                    )
                )
            ):
                raise AuditError("开发反馈不属于当前任务候选", code="identity_error")
            payload["previous_candidate"] = json.loads(
                (
                    self.directory / f"attempt-{state['attempt']}/candidate.json"
                ).read_text()
            )
            payload["failure_feedback"] = state.get("diagnosis")
            payload["checks"] = state.get("checks")
        from semflow_research.adapters.semantic_packing import pack_repair_payload

        return pack_repair_payload(payload)

    def propose(self, state):
        _kernel = self._kernel
        s = self.service
        attempt = state["attempt"] + 1
        if attempt > self.policy["repair_attempts"]:
            raise AuditError("修复候选预算耗尽", code="budget_exhausted")
        payload = self.context(state, proposing=True)
        response = frozen_call(
            s.provider,
            "repair",
            payload,
            RepairResponse,
            self.directory / f"candidate-call-{attempt}",
            _kernel=_kernel,
        )
        save_json(
            self.directory / f"attempt-{attempt}/candidate.json",
            response.model_dump(mode="json"),
        )
        s.repository.update(
            s.execution_id, phase="apply_semantic_patch", usage=s.provider.usage
        )
        return {
            "proposal": response.model_dump(mode="json"),
            "attempt": attempt,
            "proposal_hash": digest(response.model_dump(mode="json")),
        }

    def apply(self, state):
        _kernel = self._kernel
        s = self.service
        self.targets()
        response = RepairResponse.model_validate(state["proposal"])
        if (
            len({change.file for change in response.changes})
            > _kernel.spec.inputs.patch_scope.max_changed_files
        ):
            raise AuditError("候选超过冻结的修改文件上限", code="scope_error")
        if digest(state["proposal"]) != state["proposal_hash"]:
            raise AuditError("候选补丁被修改")
        attempt_dir = self.directory / f"attempt-{state['attempt']}"
        manifest = {
            "source": s.evidence.source_context.snapshot_hash,
            "proposal_hash": state["proposal_hash"],
            "allowed_paths": state["allowed_paths"],
        }
        receipt = attempt_dir / "application.json"
        if receipt.exists():
            from semflow_research.adapters.snapshot import snapshot_digest

            previous = json.loads(receipt.read_text())
            if previous["identity"] != manifest or previous[
                "workspace_hash"
            ] != snapshot_digest(attempt_dir / "workspace"):
                raise AuditError("隔离候选应用产物被修改")
            return {"applied": True}
        try:
            from semflow_research.repair.repair_inputs import verify_visible_changes

            bundle = json.loads((self.directory / "repair-context.json").read_text())
            verify_visible_changes(response.changes, bundle["file_views"])
            patch = apply_changes(
                s.evidence.root,
                attempt_dir / "workspace",
                response.changes,
                state["allowed_paths"],
            )
        except AuditError as exc:
            save_json(
                attempt_dir / "checks.json",
                {"application": {"status": "failed", "output": str(exc)}},
            )
            return {
                "applied": False,
                "checks": {"application": {"status": "failed", "output": str(exc)}},
            }
        from semflow_research.adapters.snapshot import snapshot_digest

        (attempt_dir / "repair.diff").write_text(patch)
        save_json(
            receipt,
            {
                "identity": manifest,
                "workspace_hash": snapshot_digest(attempt_dir / "workspace"),
                "diff_hash": digest(patch),
            },
        )
        return {"applied": True}

    def validate(self, state):
        _kernel = self._kernel
        from semflow_research.repair.repair_candidate_validation import (
            validate_candidate,
        )

        return validate_candidate(self, state, _kernel=_kernel)

    def diagnose(self, state):
        result = self._diagnose(state)
        save_json(
            self.directory / f"attempt-{state['attempt']}/diagnosis.json",
            result["diagnosis"],
        )
        return result

    def _diagnose(self, state):
        _kernel = self._kernel
        if state.get("applied") and all(
            value.get("status") in {"not_run", "not_evaluated"}
            for value in state["checks"].values()
        ):
            return {
                "diagnosis": {
                    "category": "inconclusive",
                    "summary": "No executed validation was selected; the patch remains unverified",
                }
            }
        from semflow_research.repair.repair_suite_checks import suite_diagnosis

        diagnosis = suite_diagnosis(state["checks"])
        if diagnosis is not None:
            return {"diagnosis": diagnosis}
        from semflow_research.repair.repair_consistency import contract_diagnosis

        diagnosis = contract_diagnosis(state["checks"])
        if diagnosis is not None:
            return {"diagnosis": diagnosis}
        rescan = state["checks"].get("rescan", {})
        if rescan.get("status") == "error":
            return {
                "diagnosis": {
                    "category": "environment"
                    if rescan.get("code") == "tool_failed"
                    else "inconclusive",
                    "summary": rescan.get(
                        "output",
                        "Static validation did not complete; do not guess a code change",
                    ),
                }
            }
        if "environment" in state["checks"] or any(
            "timeout" in str(v).lower() or "超时" in str(v)
            for v in state["checks"].values()
        ):
            return {
                "diagnosis": {
                    "category": "environment",
                    "summary": "Validation environment or resource failure; code changes cannot establish a remedy",
                }
            }
        if not state.get("applied"):
            return {
                "diagnosis": {
                    "category": "implementation",
                    "summary": "Exact patch application failed",
                    "checks": state["checks"],
                }
            }
        response = frozen_call(
            self.service.provider,
            "repair",
            {
                "phase": "diagnose_failure",
                "checks": state["checks"],
                "candidate": state["proposal"],
                "semantic_contract": self.context(state)["inspection"]["view"],
            },
            FailureDiagnosis,
            self.directory / f"diagnosis-call-{state['attempt']}",
            _kernel=_kernel,
        )
        return {"diagnosis": response.model_dump(mode="json")}

    def refresh_understanding(self, state):
        _kernel = self._kernel
        bundle = json.loads((self.directory / "repair-context.json").read_text())
        from semflow_research.repair.repair_consistency import impact_materials

        materials = [
            *bundle["inspection"]["evidence"],
            *impact_materials(self.service, state.get("checks", {}), _kernel=_kernel),
        ]
        bundle["inspection"] = self.reader.inspect(
            bundle["targets"],
            materials,
            feedback=state["diagnosis"],
            namespace=f"retry-{state['attempt']}",
            requested_behavior=bundle.get("acceptance_contract"),
            repair_scope={
                "writable_files": state["allowed_paths"],
                "meaning": "Same authorized patch targets on retry; other source remains read-only context",
            },
        )
        from semflow_research.repair.repair_inputs import patch_context

        bundle["allowed_files"], bundle["file_views"] = patch_context(
            self.service.evidence,
            state["allowed_paths"],
            bundle["inspection"]["evidence"],
        )
        save_json(
            self.directory / f"context-before-{state['attempt']}.json",
            json.loads((self.directory / "repair-context.json").read_text()),
        )
        save_json(self.directory / "repair-context.json", bundle)
        return {"context_hash": digest(bundle)}

    def finalize(self, state):
        _kernel = self._kernel
        s = self.service
        self.context(state)
        if state.get("applied"):
            from semflow_research.repair.repair_integrity import validate_application

            validate_application(
                self.directory / f"attempt-{state['attempt']}", state, s.inputs
            )
        source = self.directory / f"attempt-{state['attempt']}"
        diff = source / "repair.diff"
        if diff.exists():
            shutil.copyfile(diff, self.directory / "repair.diff")
        from semflow_research.adapters.snapshot import snapshot_digest

        workspace = source / "workspace"
        checks = {
            **state["checks"],
            "semantic_scope": {
                "status": "documented",
                "artifact": "repair-context.json",
                "context_hash": state["context_hash"],
                "attempts": state["attempt"],
                "workspace_snapshot": snapshot_digest(workspace)
                if workspace.exists()
                else None,
                "meaning": "Evidence-grounded interpretation; no additional business/security oracle executed",
            },
        }
        status = "checks_passed" if state.get("passed") else "needs_review"
        with _kernel.records.transaction() as db:
            record = db.optional_one(RepairRecord, execution_id=s.execution.id)
            if record is None:
                record = RepairRecord(
                    execution_id=s.execution.id,
                    snapshot_id=s.execution.snapshot_id,
                    candidate_ids=list(map(str, s.inputs.candidate_ids)),
                )
            record.changes, record.validation, record.status = (
                state["proposal"]["changes"],
                checks,
                status,
            )
            db.save(record)
            db.commit()
            identifier = str(record.id)
        s.repository.update(
            s.execution_id,
            status="completed",
            phase="repair_result_ready",
            result={
                "repair_id": identifier,
                "summary": state["proposal"]["summary"],
                "validation": checks,
                "status": status,
                "original_snapshot_unchanged": True,
                "diagnosis": state.get("diagnosis"),
                "semantic_view": json.loads(
                    (self.directory / "repair-context.json").read_text()
                )["inspection"]["view"],
            },
        )
        return {"saved": True, "repair_id": identifier}
