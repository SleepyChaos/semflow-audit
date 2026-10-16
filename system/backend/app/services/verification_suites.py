"""Frozen project tests stored in existing owned stage histories."""

import json
from uuid import UUID

from sqlmodel import Session

from app.adapters.artifacts import ArtifactStore
from app.adapters.repair.verification_runner import NODE_REPORTER
from app.adapters.snapshot import snapshot_digest
from app.contracts.verification import VerificationSuite
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.audit_repository import AuditRepository
from app.persistence.stage_models import Candidate
from app.persistence.stage_repository import StageRepository
from app.services.context_materials import candidate_materials, digest, save_json
from app.services.evidence import EvidenceService
from app.services.report_materials import redact

PYTEST_CONFIG = "[pytest]\n"


def target_ids(suite):
    return {
        str(identifier)
        for case in suite.cases
        if case.category == "security"
        for identifier in case.candidate_ids
    }


def candidate_scope(audit_id, identifiers):
    with Session(engine) as session:
        rows = [
            session.get(Candidate, UUID(str(identifier))) for identifier in identifiers
        ]
        if not rows or any(
            row is None or row.audit_id != audit_id or row.status != "confirmed"
            for row in rows
        ):
            raise AuditError("测试目标必须属于当前项目且仍为已确认缺陷")
        return rows


def image_default(language):
    return (
        audit_settings.VALIDATOR_PYTHON_IMAGE
        if language == "python"
        else audit_settings.VALIDATOR_JS_IMAGE
    )


def suite_identity(result):
    return {
        key: result[key] for key in ("suite", "image", "snapshot_hash", "candidate_ids")
    }


def freeze_suite(stage, suite, image, origin):
    audit = AuditRepository().get(str(stage.audit_id))
    candidate_scope(
        stage.audit_id,
        {str(identifier) for case in suite.cases for identifier in case.candidate_ids},
    )
    if suite.language != audit.language:
        raise AuditError("测试语言与项目不匹配")
    if (
        snapshot_digest(ArtifactStore().source(str(audit.source_run_id)))
        != audit.snapshot_hash
    ):
        raise AuditError("原始快照变化，不能冻结测试")
    result = {
        "suite": suite.model_dump(mode="json"),
        "image": image or image_default(audit.language),
        "snapshot_hash": audit.snapshot_hash,
        "candidate_ids": sorted(target_ids(suite)),
        "origin": origin,
    }
    result["suite_hash"] = digest(suite_identity(result))
    directory = ArtifactStore().directory(str(stage.id))
    files = directory / "tests"
    files.mkdir(exist_ok=False)
    for name, content in suite.files.items():
        if suite.language == "python":
            compile(content, name, "exec")
        (files / name).write_text(content, encoding="utf-8")
    (files / "pytest.ini").write_text(PYTEST_CONFIG, encoding="utf-8")
    if suite.language == "javascript":
        (files / "verification-reporter.cjs").write_text(
            NODE_REPORTER, encoding="utf-8"
        )
    result["test_files_hash"] = snapshot_digest(files)
    save_json(directory / "suite.json", result)
    return result


def read_suite(identifier, audit_id):
    stage = StageRepository().get(str(identifier))
    if (
        stage.audit_id != audit_id
        or stage.kind != "verification_suite"
        or stage.status != "completed"
    ):
        raise AuditError("测试集不存在、不属于当前项目或尚未生成")
    directory = ArtifactStore().directory(str(stage.id))
    saved = json.loads((directory / "suite.json").read_text(encoding="utf-8"))
    if (
        saved != stage.result
        or digest(suite_identity(saved)) != saved["suite_hash"]
        or snapshot_digest(directory / "tests") != saved["test_files_hash"]
    ):
        raise AuditError("测试内容或运行环境记录变化，请创建新的测试集")
    suite = VerificationSuite.model_validate(saved["suite"])
    return stage, suite, directory / "tests"


class SuiteService:
    def __init__(self, stage_id, provider):
        self.stage_id, self.provider = stage_id, provider
        self.repository = StageRepository()
        self.stage = self.repository.get(stage_id)

    def run(self):
        stage = self.stage
        self.repository.active(self.stage_id)
        targets = candidate_scope(stage.audit_id, stage.inputs["candidate_ids"])
        source = EvidenceService(str(stage.audit_id), self.stage_id, [])
        if snapshot_digest(source.root) != source.audit.snapshot_hash:
            raise AuditError("原始快照变化，不能生成测试")
        evidence = candidate_materials(source, targets)
        files = {}
        for target in targets:
            name = target.location.get("file")
            if name:
                from app.adapters.repair.patches import safe_file

                path = safe_file(source.root, name)
                if path.is_file() and path.stat().st_size <= 25000:
                    files[name] = path.read_text(encoding="utf-8")
        payload = redact(
            {
                "language": source.audit.language,
                "snapshot_hash": source.audit.snapshot_hash,
                "candidates": [row.model_dump(mode="json") for row in targets],
                "required_candidate_ids": [str(row.id) for row in targets],
                "evidence": evidence,
                "source_files": files,
                "business_requirements": stage.inputs.get("requirements", ""),
                "runtime": {
                    "source": "/workspace",
                    "tests": "/suite",
                    "network": "none",
                    "read_only": True,
                },
            }
        )
        if len(json.dumps(payload).encode()) > 60000:
            raise AuditError("测试生成材料过大，请减少目标；没有省略目标后假装验证")
        self.repository.update(self.stage_id, phase="generate_verification_suite")
        expected = {str(row.id) for row in targets}
        for attempt in range(2):
            self.repository.active(self.stage_id)
            suite = self.provider.generate(
                "verification_suite", payload, VerificationSuite
            )
            all_ids = {
                str(identifier)
                for case in suite.cases
                for identifier in case.candidate_ids
            }
            if target_ids(suite) == expected and all_ids.issubset(expected):
                break
            if attempt:
                raise AuditError("测试遗漏或引用了其他漏洞候选")
            payload["coverage_feedback"] = {
                "missing_security_candidate_ids": sorted(expected - target_ids(suite)),
                "unexpected_candidate_ids": sorted(all_ids - expected),
                "instruction": "Regenerate the complete executable suite. Its security cases must cover every required_candidate_id exactly within the authorized set; one case may cite duplicate candidates for the same actual behavior. Do not drop assertions, skip tests or alter the implementation.",
            }
        result = freeze_suite(
            stage, suite, stage.inputs.get("image", ""), "ai_generated"
        )
        self.repository.update(
            self.stage_id,
            status="completed",
            phase="verification_suite_ready",
            result=result,
            model=self.provider.model,
            usage=self.provider.usage,
        )
