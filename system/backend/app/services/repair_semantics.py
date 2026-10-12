"""Semantic repair: fixed source, evidence contract and bounded complete candidates."""

import json
import shutil

from sqlmodel import Session, select

from app.adapters.repair.patches import apply_changes, safe_file
from app.contracts.repair_semantics import FailureDiagnosis
from app.contracts.stages import RepairResponse
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.stage_models import Candidate, RepairRecord
from app.services.context_materials import (
    candidate_materials,
    digest,
    frozen_call,
    save_json,
    semantic_policy,
    verify_snapshot,
)
from app.services.semantic_inspection import SemanticInspection


class SemanticRepair:
    def __init__(self, service):
        self.service = service
        self.directory = service.directory
        self.policy = semantic_policy(self.directory)
        self.reader = SemanticInspection(
            service.evidence,
            service.provider,
            self.directory,
            service.repository,
            "repair",
        )

    def targets(self):
        s = self.service
        with Session(engine) as db:
            targets = db.exec(
                select(Candidate).where(
                    Candidate.audit_id == s.stage.audit_id,
                    Candidate.id.in_(s.inputs.candidate_ids),
                )
            ).all()
        if len(targets) != len(set(s.inputs.candidate_ids)) or any(
            t.status != "confirmed" for t in targets
        ):
            raise AuditError("修复目标确认状态变化或不属于本审计")
        verify_snapshot(s.evidence)
        return targets

    def prepare(self, _):
        s = self.service
        targets = self.targets()
        materials = candidate_materials(s.evidence, targets)
        if not any(m["kind"] == "code" for m in materials):
            for target in targets:
                if target.location.get("file"):
                    line = max(1, target.location.get("line", 1))
                    materials.append(
                        s.evidence.read(
                            target.location["file"], max(1, line - 15), line + 35
                        )
                    )
        paths = (
            s.inputs.allowed_paths
            or sorted({t.location["file"] for t in targets if t.location.get("file")})
            or sorted(
                {
                    m["reference"]["file"]
                    for m in materials
                    if m["kind"] == "code"
                    and m["reference"]["file"].endswith(
                        (".py", ".js", ".jsx", ".ts", ".tsx")
                    )
                }
            )
        )
        if not paths or len(paths) > 30:
            raise AuditError("需要明确有限的可修改文件")
        contents = {}
        for name in paths:
            path = safe_file(s.evidence.root, name)
            if not path.is_file() or path.stat().st_size > 100000:
                raise AuditError("修复文件无效或超过预算")
            contents[name] = path.read_text()
        if len(json.dumps(contents, ensure_ascii=False)) > 24000:
            raise AuditError(
                "必要修改代码超过上下文预算，请减少目标或文件", code="context_budget"
            )
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
        inspection = self.reader.inspect(descriptions, materials)
        bundle = {
            "targets": descriptions,
            "target_identities": {
                str(t.id): digest(t.model_dump(mode="json")) for t in targets
            },
            "allowed_files": contents,
            "materials": materials,
            "inspection": inspection,
            "snapshot": s.evidence.audit.snapshot_hash,
            "validation_profile": s.inputs.validation_profile,
            "validation_limit": "Existing syntax/project tests and optional static rescan only; no new exploit oracle",
        }
        save_json(self.directory / "repair-context.json", bundle)
        s.repository.update(
            s.stage_id,
            phase="semantic_context_ready",
            model=s.provider.model,
            result={"semantic_artifact": "repair-context.json", "allowed_paths": paths},
        )
        return {"context_hash": digest(bundle), "attempt": 0, "allowed_paths": paths}

    def context(self, state):
        bundle = json.loads((self.directory / "repair-context.json").read_text())
        if digest(bundle) != state["context_hash"]:
            raise AuditError("修复语义上下文被修改")
        targets = self.targets()
        if bundle["target_identities"] != {
            str(t.id): digest(t.model_dump(mode="json")) for t in targets
        }:
            raise AuditError("修复目标内容已变化")
        payload = {**bundle, "phase": "propose_patch"}
        # Full permitted files already contain these windows; keep their exact citations.
        inspection = dict(bundle["inspection"])
        inspection["evidence"] = [
            {
                **row,
                "content": "See exact allowed_files content; original evidence stored in context artifact",
            }
            if row["kind"] == "code"
            and row["reference"].get("file") in bundle["allowed_files"]
            else row
            for row in inspection["evidence"]
        ]
        payload["inspection"] = inspection
        payload.pop("materials")
        if state.get("attempt"):
            payload["previous_candidate"] = json.loads(
                (
                    self.directory / f"attempt-{state['attempt']}/candidate.json"
                ).read_text()
            )
            payload["failure_feedback"] = state.get("diagnosis")
            payload["checks"] = state.get("checks")
        return payload

    def propose(self, state):
        s = self.service
        attempt = state["attempt"] + 1
        if attempt > self.policy["repair_attempts"]:
            raise AuditError("修复候选预算耗尽", code="budget_exhausted")
        payload = self.context(state)
        response = frozen_call(
            s.provider,
            "repair",
            payload,
            RepairResponse,
            self.directory / f"candidate-call-{attempt}",
        )
        save_json(
            self.directory / f"attempt-{attempt}/candidate.json",
            response.model_dump(mode="json"),
        )
        s.repository.update(
            s.stage_id, phase="apply_semantic_patch", usage=s.provider.usage
        )
        return {
            "proposal": response.model_dump(mode="json"),
            "attempt": attempt,
            "proposal_hash": digest(response.model_dump(mode="json")),
        }

    def apply(self, state):
        s = self.service
        self.targets()
        response = RepairResponse.model_validate(state["proposal"])
        if digest(state["proposal"]) != state["proposal_hash"]:
            raise AuditError("候选补丁被修改")
        attempt_dir = self.directory / f"attempt-{state['attempt']}"
        manifest = {
            "source": s.evidence.audit.snapshot_hash,
            "proposal_hash": state["proposal_hash"],
            "allowed_paths": state["allowed_paths"],
        }
        receipt = attempt_dir / "application.json"
        if receipt.exists():
            from app.adapters.snapshot import snapshot_digest

            previous = json.loads(receipt.read_text())
            if previous["identity"] != manifest or previous[
                "workspace_hash"
            ] != snapshot_digest(attempt_dir / "workspace"):
                raise AuditError("隔离候选应用产物被修改")
            return {"applied": True}
        try:
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
        from app.adapters.snapshot import snapshot_digest

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
        s = self.service
        directory = self.directory / f"attempt-{state['attempt']}"
        from app.services.repair_integrity import validate_application

        identity = validate_application(directory, state, s.inputs)
        saved = directory / "checks.json"
        validation_receipt = directory / "validation-receipt.json"
        if saved.exists():
            checks = json.loads(saved.read_text())
            receipt = json.loads(validation_receipt.read_text())
            if receipt["identity"] != identity or receipt["checks_hash"] != digest(
                checks
            ):
                raise AuditError("候选验证产物已变化")
        else:
            previous = s.directory
            try:
                s.directory = directory
                checks = s.validate(state)["checks"]
            except AuditError as exc:
                # Runtime setup failure must never become implementation feedback.
                checks = {"environment": {"status": "blocked", "output": str(exc)}}
            finally:
                s.directory = previous
            save_json(saved, checks)
            save_json(
                validation_receipt,
                {"identity": identity, "checks_hash": digest(checks)},
            )
        passed = all(
            v["status"] == "passed"
            or (name == "rescan" and not s.inputs.rescan and v["status"] == "not_run")
            for name, v in checks.items()
        )
        return {"checks": checks, "passed": passed}

    def diagnose(self, state):
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
        )
        return {"diagnosis": response.model_dump(mode="json")}

    def refresh_understanding(self, state):
        bundle = json.loads((self.directory / "repair-context.json").read_text())
        bundle["inspection"] = self.reader.inspect(
            bundle["targets"],
            bundle["inspection"]["evidence"],
            feedback=state["diagnosis"],
            namespace=f"retry-{state['attempt']}",
        )
        save_json(
            self.directory / f"context-before-{state['attempt']}.json",
            json.loads((self.directory / "repair-context.json").read_text()),
        )
        save_json(self.directory / "repair-context.json", bundle)
        return {"context_hash": digest(bundle)}

    def finalize(self, state):
        s = self.service
        self.context(state)
        if state.get("applied"):
            from app.services.repair_integrity import validate_application

            validate_application(
                self.directory / f"attempt-{state['attempt']}", state, s.inputs
            )
        source = self.directory / f"attempt-{state['attempt']}"
        diff = source / "repair.diff"
        if diff.exists():
            shutil.copyfile(diff, self.directory / "repair.diff")
        from app.adapters.snapshot import snapshot_digest

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
        with Session(engine) as db:
            record = db.exec(
                select(RepairRecord).where(RepairRecord.stage_id == s.stage.id)
            ).one_or_none()
            if record is None:
                record = RepairRecord(
                    stage_id=s.stage.id,
                    audit_id=s.stage.audit_id,
                    candidate_ids=list(map(str, s.inputs.candidate_ids)),
                )
            record.changes, record.validation, record.status = (
                state["proposal"]["changes"],
                checks,
                status,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            identifier = str(record.id)
        s.repository.update(
            s.stage_id,
            status="completed",
            phase="awaiting_patch_acceptance",
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
        if s.inputs.verification_suite_id and workspace.exists():
            from app.services.repair_comparison import enqueue_after_repair
            enqueue_after_repair(identifier, s.inputs.verification_suite_id)
        return {"saved": True, "repair_id": identifier}
