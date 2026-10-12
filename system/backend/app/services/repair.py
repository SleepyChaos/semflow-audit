from uuid import UUID

from sqlmodel import Session, select

from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.sarif import parse_sarif
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.repair.patches import apply_changes, safe_file
from app.adapters.repair.validator import validate_workspace
from app.adapters.snapshot import snapshot_digest
from app.contracts.stages import RepairRequest, RepairResponse
from app.core.db import engine
from app.domain.audit import AuditError, ScanPlan
from app.persistence.stage_models import Candidate, RepairRecord
from app.persistence.stage_repository import StageRepository
from app.ports.model import ModelProvider
from app.services.evidence import EvidenceService, valid_evidence


class RepairService:
    def __init__(self, stage_id: str, provider: ModelProvider):
        self.stage_id, self.provider = stage_id, provider
        self.repository = StageRepository()
        self.stage = self.repository.get(stage_id)
        self.inputs = RepairRequest.model_validate(self.stage.inputs)
        self.evidence = EvidenceService(str(self.stage.audit_id), stage_id, [])
        self.directory = ArtifactStore().directory(stage_id)

    def plan(self) -> dict:
        self.repository.active(self.stage_id)
        with Session(engine) as session:
            candidates = session.exec(
                select(Candidate).where(
                    Candidate.audit_id == self.stage.audit_id,
                    Candidate.id.in_(self.inputs.candidate_ids),
                )
            ).all()
        if len(candidates) != len(set(self.inputs.candidate_ids)) or any(
            row.status != "confirmed" for row in candidates
        ):
            raise AuditError("修复只能针对本次审计中已由人工确认的候选")
        files = set(self.inputs.allowed_paths)
        evidence = []
        for candidate in candidates:
            rows = valid_evidence(
                candidate.audit_id,
                [UUID(identifier) for identifier in candidate.evidence_ids],
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
            self.stage_id,
            phase="generate_diff",
            model=self.provider.model,
            result={"allowed_paths": sorted(files)},
        )
        response = self.provider.generate(
            "repair",
            {
                "snapshot_hash": self.evidence.audit.snapshot_hash,
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
        self.repository.update(self.stage_id, usage=self.provider.usage)
        return {
            "proposal": response.model_dump(mode="json"),
            "allowed_paths": sorted(files),
        }

    def apply(self, state: dict) -> dict:
        self.repository.active(self.stage_id)
        if snapshot_digest(self.evidence.root) != self.evidence.audit.snapshot_hash:
            raise AuditError("补丁生成过程中原始快照发生变化")
        with Session(engine) as session:
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
        with Session(engine) as session:
            record = RepairRecord(
                stage_id=self.stage.id,
                audit_id=self.stage.audit_id,
                candidate_ids=[
                    str(identifier) for identifier in self.inputs.candidate_ids
                ],
                changes=[change.model_dump() for change in response.changes],
            )
            session.add(record)
            session.commit()
            session.refresh(record)
        self.repository.update(self.stage_id, phase="validate")
        return {"repair_id": str(record.id)}

    def validate(self, state: dict) -> dict:
        self.repository.active(self.stage_id)
        workspace = self.directory / "workspace"
        patched_hash = snapshot_digest(workspace)
        checks = {
            "isolated_tests": validate_workspace(
                workspace, self.evidence.audit.language, self.inputs.validation_profile
            )
        }
        if self.inputs.rescan:
            scanner = CodeQLScanner()
            audit = self.evidence.audit
            plan = ScanPlan(audit.language, audit.query_pack, audit.suite)
            scanner.create_database(
                workspace,
                self.directory / "patched-database",
                self.directory / "execution.log",
                plan,
            )
            scanner.analyze(
                self.directory / "patched-database",
                self.directory / "patched.sarif",
                self.directory / "execution.log",
                plan,
            )
            findings = parse_sarif(
                self.directory / "patched.sarif",
                patched_hash,
            )
            for rule_id in audit.custom_rule_ids:
                from app.adapters.codeql.custom import prepare_query, run_query
                from app.services.rules_execution import owned_published_rule

                rule = owned_published_rule(
                    UUID(rule_id), audit.owner_id, audit.language, allow_retired=True
                )
                pack = self.directory / "patched-supplements" / rule_id / "pack"
                prepare_query(
                    pack, audit.language, rule.query, rule.modules, rule.dependencies
                )
                findings.extend(
                    run_query(
                        self.directory / "patched-database",
                        pack,
                        pack.parent / "results.sarif",
                        self.directory / "execution.log",
                        patched_hash,
                    )
                )
            with Session(engine) as session:
                targets = [
                    session.get(Candidate, identifier)
                    for identifier in self.inputs.candidate_ids
                ]
            target_static_ids = {
                candidate.static_finding_id
                for candidate in targets
                if candidate.static_finding_id
            }
            rules = {
                finding["rule"]
                for finding in audit.findings
                if finding["id"] in target_static_ids
            }
            remaining = [finding for finding in findings if finding["rule"] in rules]
            baseline_rules = {finding["rule"] for finding in audit.findings}
            new_rule_alerts = [
                finding for finding in findings if finding["rule"] not in baseline_rules
            ]
            checks["rescan"] = {
                "status": "passed"
                if rules and not remaining and not new_rule_alerts
                else "needs_review",
                "findings": findings,
                "remaining_target_rules": sorted(
                    {finding["rule"] for finding in remaining}
                ),
                "new_rule_alerts": new_rule_alerts,
                "codeql_version": scanner.version(),
                "patched_snapshot_hash": patched_hash,
                "meaning": "absence of selected rule alerts is not independent proof of remediation",
            }
        else:
            checks["rescan"] = {"status": "not_run", "reason": "用户未选择复扫"}
        if snapshot_digest(workspace) != patched_hash:
            raise AuditError("验证过程中修复副本发生变化；结果失效")
        checks["isolated_tests"]["patched_snapshot_hash"] = patched_hash
        self.repository.update(self.stage_id, phase="save_validation")
        return {"checks": checks}

    def save(self, state: dict) -> dict:
        self.repository.active(self.stage_id)
        status = (
            "checks_passed"
            if all(check["status"] == "passed" for check in state["checks"].values())
            else "needs_review"
        )
        with Session(engine) as session:
            record = session.get(RepairRecord, UUID(state["repair_id"]))
            record.validation, record.status = state["checks"], status
            session.add(record)
            session.commit()
        self.repository.update(
            self.stage_id,
            status="completed",
            phase="awaiting_patch_acceptance",
            result={
                "repair_id": state["repair_id"],
                "summary": state["proposal"]["summary"],
                "validation": state["checks"],
                "status": status,
                "original_snapshot_unchanged": True,
            },
        )
        if self.inputs.verification_suite_id:
            from app.services.repair_comparison import enqueue_after_repair

            enqueue_after_repair(state["repair_id"], self.inputs.verification_suite_id)
        return {"saved": True}
