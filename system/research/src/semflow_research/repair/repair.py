"""Algorithm extracted from app.services.repair.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

from uuid import UUID

from semflow_contracts.modelio.stages import RepairRequest, RepairResponse

from semflow_research.adapters.artifacts import ArtifactStore
from semflow_research.adapters.repair.patches import apply_changes, safe_file
from semflow_research.adapters.repair.validator import validate_workspace
from semflow_research.adapters.snapshot import snapshot_digest
from semflow_research.domain.errors import AuditError
from semflow_research.evidence.evidence import EvidenceService, valid_evidence
from semflow_research.ports.model import ModelProvider
from semflow_research.state.models import Candidate, RepairRecord


class RepairService:
    def __init__(self, execution_id: str, provider: ModelProvider, *, _kernel):
        self._kernel = _kernel
        self.execution_id, self.provider = (execution_id, provider)
        self.repository = _kernel.execution_records
        self.execution = self.repository.get(execution_id)
        self.inputs = RepairRequest.model_validate(self.execution.inputs)
        self.evidence = EvidenceService(
            str(self.execution.snapshot_id), execution_id, [], _kernel=_kernel
        )
        self.directory = ArtifactStore(_kernel=_kernel).directory(execution_id)

    def plan(self) -> dict:
        _kernel = self._kernel
        self.repository.active(self.execution_id)
        with _kernel.records.transaction() as session:
            candidates = session.list(
                Candidate,
                snapshot_id=self.execution.snapshot_id,
                id__in=self.inputs.candidate_ids,
            )
        if len(candidates) != len(set(self.inputs.candidate_ids)) or any(
            row.status != "confirmed" for row in candidates
        ):
            raise AuditError("修复只能针对本次审计中已由人工确认的候选")
        files = set(self.inputs.allowed_paths)
        evidence = []
        for candidate in candidates:
            rows = valid_evidence(
                candidate.snapshot_id,
                [UUID(identifier) for identifier in candidate.evidence_ids],
                _kernel=_kernel,
            )
            for row in rows:
                evidence.append(
                    {
                        "id": str(row.id),
                        "reference": row.reference,
                        "content": row.content,
                    }
                )
                if row.kind == "code":
                    files.add(row.reference["file"])
        if not files or len(files) > 30:
            raise AuditError("需要明确且有限的修复文件范围")
        contents = {}
        for name in files:
            path = safe_file(self.evidence.root, name)
            if not path.is_file() or path.stat().st_size > 100000:
                raise AuditError("修复文件不存在或超过上下文限制")
            contents[name] = path.read_text()
        if sum(map(len, contents.values())) > 100000:
            raise AuditError("修复上下文过大，请减少目标")
        self.repository.update(
            self.execution_id,
            phase="generate_diff",
            model=self.provider.model,
            result={"allowed_paths": sorted(files)},
        )
        response = self.provider.generate(
            "repair",
            {
                "snapshot_hash": self.evidence.source_context.snapshot_hash,
                "candidates": [
                    {
                        "id": str(row.id),
                        "title": row.title,
                        "description": row.description,
                    }
                    for row in candidates
                ],
                "evidence": evidence,
                "allowed_files": contents,
            },
            RepairResponse,
        )
        self.repository.update(self.execution_id, usage=self.provider.usage)
        return {
            "proposal": response.model_dump(mode="json"),
            "allowed_paths": sorted(files),
        }

    def apply(self, state: dict) -> dict:
        _kernel = self._kernel
        self.repository.active(self.execution_id)
        if (
            snapshot_digest(self.evidence.root)
            != self.evidence.source_context.snapshot_hash
        ):
            raise AuditError("补丁生成过程中原始快照发生变化")
        with _kernel.records.transaction() as session:
            candidates = [
                session.get(Candidate, identifier)
                for identifier in self.inputs.candidate_ids
            ]
            if any(row is None or row.status != "confirmed" for row in candidates):
                raise AuditError("修复目标确认状态已变化")
        response = RepairResponse.model_validate(state["proposal"])
        diff = apply_changes(
            self.evidence.root,
            self.directory / "workspace",
            response.changes,
            state["allowed_paths"],
        )
        (self.directory / "repair.diff").write_text(diff)
        with _kernel.records.transaction() as session:
            record = RepairRecord(
                execution_id=self.execution.id,
                snapshot_id=self.execution.snapshot_id,
                candidate_ids=[
                    str(identifier) for identifier in self.inputs.candidate_ids
                ],
                changes=[change.model_dump() for change in response.changes],
            )
            session.save(record)
            session.commit()
        self.repository.update(self.execution_id, phase="validate")
        return {"repair_id": str(record.id)}

    def validate(self, state: dict) -> dict:
        _kernel = self._kernel
        self.repository.active(self.execution_id)
        workspace = self.directory / "workspace"
        patched_hash = snapshot_digest(workspace)
        # Interface peer: RepairValidationPlan in semflow_contracts.repair.
        # AGENT: syntax and project tests are independent requested controls;
        # do not substitute a test run for syntax or execute a disabled check.
        plan = _kernel.spec.inputs.validation_plan
        checks = {}
        if plan.syntax:
            checks["syntax"] = validate_workspace(
                workspace,
                self.evidence.source_context.language,
                "syntax",
                _kernel=_kernel,
            )
        if plan.project_tests is not None:
            checks["isolated_tests"] = validate_workspace(
                workspace,
                self.evidence.source_context.language,
                plan.project_tests.runner,
                _kernel=_kernel,
            )
        if self.inputs.rescan:
            from semflow_research.repair.rescan import check

            checks["rescan"] = check(self, workspace, patched_hash, _kernel=_kernel)
        else:
            checks["rescan"] = {"status": "not_run", "reason": "用户未选择复扫"}
        if snapshot_digest(workspace) != patched_hash:
            raise AuditError("验证过程中修复副本发生变化；结果失效")
        for check in checks.values():
            check["patched_snapshot_hash"] = patched_hash
        self.repository.update(self.execution_id, phase="save_validation")
        return {"checks": checks}

    def save(self, state: dict) -> dict:
        _kernel = self._kernel
        self.repository.active(self.execution_id)
        status = (
            "checks_passed"
            if all(check["status"] == "passed" for check in state["checks"].values())
            else "needs_review"
        )
        with _kernel.records.transaction() as session:
            record = session.get(RepairRecord, UUID(state["repair_id"]))
            record.validation, record.status = (state["checks"], status)
            session.save(record)
            session.commit()
        self.repository.update(
            self.execution_id,
            status="completed",
            phase="repair_result_ready",
            result={
                "repair_id": state["repair_id"],
                "summary": state["proposal"]["summary"],
                "validation": state["checks"],
                "status": status,
                "original_snapshot_unchanged": True,
            },
        )
        return {"saved": True}
