"""Per-audit AI reports with frozen input, budget, evidence binding and freshness."""

import hashlib
import json

from sqlmodel import Session

from app.adapters.artifacts import ArtifactStore
from app.contracts.ai_report import AIReportResponse
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.audit_repository import AuditRepository
from app.persistence.stage_repository import StageRepository
from app.services.report_materials import combine_reports, redact, report_batches
from app.services.report_overview import overview_material


def report_source(report: dict, *, scrub: bool = True) -> dict:
    audit = report["audit"]
    candidate_ids = {
        row["candidate_id"]
        for row in report.get("reader_guide", {}).get("candidates", [])
    }
    candidates = [
        {k: v for k, v in row.items() if k != "explanation"}
        for row in report.get("candidates", [])
        if not candidate_ids or row["id"] in candidate_ids
    ]
    evidence_ids = {item for row in candidates for item in row.get("evidence_ids", [])}
    material = {
        "audit": {
            k: audit.get(k)
            for k in (
                "id",
                "project_name",
                "snapshot_hash",
                "language",
                "status",
                "error",
                "findings",
            )
        },
        "summary": report.get("summary", {}),
        "coverage": report.get("coverage", {}),
        "candidates": candidates,
        "evidence": [
            row for row in report.get("evidence", []) if row["id"] in evidence_ids
        ],
        "decisions": report.get("decisions", []),
        "repairs": report.get("repairs", []),
        "verification": report.get("verification", []),
        "rules": [
            {k: row.get(k) for k in ("id", "title", "status", "validation")}
            for row in report.get("rules", [])
        ],
        "assessments": [
            {
                key: row.get(key)
                for key in (
                    "candidate_id",
                    "assessment",
                    "reason",
                    "evidence_ids",
                    "checked_premises",
                    "missing_premises",
                    "counterevidence_ids",
                    "runtime_unknowns",
                    "premises",
                    "weakness",
                    "security_property",
                    "detail",
                )
            }
            for stage in report.get("stages", [])
            if stage.get("kind") == "review"
            for batch in stage.get("result", {}).get("batches", [])
            for row in batch.get("assessments", [])
            if row.get("candidate_id") in candidate_ids or not candidate_ids
        ],
        "review_context": [
            {
                "stage_id": row.get("id"),
                "status": row.get("status"),
                "coverage_status": row.get("result", {}).get("coverage_status"),
                "stop_reason": row.get("result", {}).get("stop_reason"),
                "unreviewed_candidate_ids": row.get("result", {}).get(
                    "unreviewed_candidate_ids", []
                ),
                "root_relations": row.get("result", {}).get("root_relations", []),
            }
            for row in report.get("stages", [])
            if row.get("kind") == "review"
        ],
        "stages": [
            {k: row.get(k) for k in ("id", "kind", "status", "phase", "error")}
            for row in report.get("stages", [])
            if row.get("kind") != "report"
        ],
    }
    return redact(material) if scrub else material


def source_fingerprint(report: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            report_source(report, scrub=False), ensure_ascii=False, sort_keys=True
        ).encode()
    ).hexdigest()


def validate_response(response: AIReportResponse, source: dict):
    candidates = {row["id"]: row for row in source["candidates"]}
    identifiers = [item.candidate_id for item in response.issues]
    if len(identifiers) != len(set(identifiers)) or set(identifiers) != set(candidates):
        raise AuditError(
            "AI 报告遗漏、重复或新增了候选，不能作为完整报告",
            code="report_identity_error",
        )
    known = {row["id"] for row in source["evidence"]}
    for issue in response.issues:
        permitted = set(candidates[issue.candidate_id].get("evidence_ids", [])) & known
        if not set(issue.evidence_ids).issubset(permitted) or (
            permitted and not issue.evidence_ids
        ):
            raise AuditError(
                "AI 报告引用了未关联的证据，需重新生成", code="report_evidence_error"
            )


def report_state(stages: list, fingerprint: str) -> dict:
    reports = [row for row in stages if row.kind == "report"]
    reports.sort(key=lambda row: row.created_at, reverse=True)
    latest = reports[0] if reports else None
    if (
        latest
        and latest.status != "completed"
        and latest.inputs.get("source_fingerprint") == fingerprint
    ):
        return {
            "status": latest.status,
            "stage_id": str(latest.id),
            "error": latest.error,
        }
    current = next(
        (
            row
            for row in reports
            if row.status == "completed"
            and row.result.get("source_fingerprint") == fingerprint
        ),
        None,
    )
    if current:
        return {
            "status": "ready",
            "stage_id": str(current.id),
            "model": current.model,
            "created_at": current.created_at.isoformat(),
            "narrative": current.result["narrative"],
        }
    latest = reports[0] if reports else None
    return {
        "status": "missing"
        if latest is None
        else "stale"
        if latest.status == "completed"
        else latest.status,
        "stage_id": str(latest.id) if latest else None,
        "error": latest.error if latest else None,
        "narrative": latest.result.get("narrative")
        if latest and latest.status == "completed"
        else None,
    }


class ReportService:
    def __init__(self, stage_id, provider):
        self.stage_id, self.provider = stage_id, provider
        self.repository = StageRepository()
        self.stage = self.repository.get(stage_id)
        self.audit = AuditRepository().get(str(self.stage.audit_id))
        self.directory = ArtifactStore().directory(stage_id)

    def current(self):
        from app.services.reports import build_report

        with Session(engine) as session:
            self.audit = AuditRepository().get(str(self.stage.audit_id))
            return build_report(session, self.audit)

    def prepare(self, _state):
        self.repository.active(self.stage_id)
        report = self.current()
        fingerprint = source_fingerprint(report)
        if fingerprint != self.stage.inputs["source_fingerprint"]:
            raise AuditError(
                "报告生成前审计结果已变化，请重新生成", code="report_stale"
            )
        source = report_source(report)
        # Recheck cited records against their real immutable source before sending.
        if source["evidence"]:
            from uuid import UUID

            from app.services.evidence import valid_evidence

            valid_evidence(
                self.audit.id, [UUID(row["id"]) for row in source["evidence"]], False
            )
        path = self.directory / "report-source.json"
        path.write_text(
            json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.repository.update(self.stage_id, phase="write_chinese_report")
        return {
            "source_fingerprint": fingerprint,
            "material_fingerprint": hashlib.sha256(
                json.dumps(source, ensure_ascii=False, sort_keys=True).encode()
            ).hexdigest(),
        }

    def generate(self, state):
        self.repository.active(self.stage_id)
        source = json.loads(
            (self.directory / "report-source.json").read_text(encoding="utf-8")
        )
        actual = hashlib.sha256(
            json.dumps(source, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        if actual != state["material_fingerprint"]:
            raise AuditError("报告冻结材料被修改，不能继续生成", code="integrity_error")
        responses = []
        batches = [overview_material(source), *report_batches(source)]
        for index, batch in enumerate(batches):
            self.repository.active(self.stage_id)
            self.repository.update(self.stage_id, phase="write_chinese_report")
            response = self.provider.generate("report", batch, AIReportResponse)
            validate_response(response, batch)
            responses.append(response)
            name = (
                "report-overview.json" if index == 0 else f"report-batch-{index}.json"
            )
            (self.directory / name).write_text(
                json.dumps(response.model_dump(mode="json"), ensure_ascii=False),
                encoding="utf-8",
            )
        return {"narrative": combine_reports(responses[1:], responses[0])}

    def save(self, state):
        self.repository.active(self.stage_id)
        if source_fingerprint(self.current()) != state["source_fingerprint"]:
            raise AuditError(
                "生成期间判断或验证结果已变化，请重新生成报告", code="report_stale"
            )
        result = {
            "source_fingerprint": state["source_fingerprint"],
            "narrative": state["narrative"],
        }
        (self.directory / "ai-report.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.repository.update(
            self.stage_id,
            status="completed",
            phase="chinese_report_ready",
            result=result,
            model=self.provider.model,
            usage=self.provider.usage,
        )
        return {"saved": True}
