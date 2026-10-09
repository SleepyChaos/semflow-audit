"""Independent scan branches and one join; no failed branch is an empty success."""

from uuid import UUID

from sqlmodel import Session, select

from app.adapters.ai.provider import CompatibleModel
from app.contracts.scouting import ScoutRequest
from app.core.db import engine
from app.domain.audit import AuditCancelled
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import StageRun
from app.persistence.stage_repository import StageCancelled, StageRepository
from app.services.scouting import ScoutService
from app.workflows.scouting import build_scout_graph


def ensure_scout_stage(run_id: str) -> str:
    with Session(engine) as db:
        run = db.exec(
            select(AuditRun).where(AuditRun.id == UUID(run_id)).with_for_update()
        ).one()
        if run.status == "cancelled":
            raise AuditCancelled("审计已取消")
        stage_id = run.coverage.get("dual_engine", {}).get("scout_stage_id")
        if stage_id:
            stage = db.get(StageRun, UUID(stage_id))
            if stage is None or stage.audit_id != run.id or stage.kind != "scout":
                raise ValueError("Independent scout stage identity mismatch")
            return stage_id
        stage = StageRun(
            audit_id=run.id,
            kind="scout",
            prompt_version="7",
            inputs=ScoutRequest().model_dump(mode="json"),
        )
        db.add(stage)
        db.flush()
        run.coverage = {
            **run.coverage,
            "dual_engine": {"status": "running", "scout_stage_id": str(stage.id)},
        }
        db.add(run)
        db.commit()
        return str(stage.id)


class DualScanService:
    def __init__(self, scanner_service, provider_factory=CompatibleModel):
        self.scan_service = scanner_service
        self.artifacts = scanner_service.artifacts
        self.repository = scanner_service.repository
        self.provider_factory = provider_factory

    def codeql(self, state):
        run_id = state["run_id"]
        try:
            self.scan_service.create_database(run_id)
            self.scan_service.scan(run_id)
            self.scan_service.save_findings(run_id, finalize=False)
            outcome = {"status": "completed"}
        except AuditCancelled:
            raise
        except Exception as exc:
            outcome = {
                "status": "failed",
                "error": str(exc)[:1000],
                "error_type": type(exc).__name__,
            }
        return {"codeql_outcome": outcome}

    def scout(self, state):
        stage_id = ensure_scout_stage(state["run_id"])
        repository, provider = StageRepository(), None
        stage = repository.get(stage_id)
        if stage.status == "completed":
            return {
                "scout_outcome": {
                    "stage_id": stage_id,
                    "status": "completed",
                    "coverage": stage.result.get("coverage", {}),
                }
            }
        if not repository.claim(stage_id):
            return {"scout_outcome": {"stage_id": stage_id, "status": stage.status}}
        try:
            provider = self.provider_factory()
            if hasattr(provider, "bind_stage"):
                provider.bind_stage(stage_id, stage.prompt_version)
            service = ScoutService(stage_id, provider)
            build_scout_graph(service).invoke({"stage_id": stage_id})
            stage = repository.get(stage_id)
            outcome = {
                "stage_id": stage_id,
                "status": stage.status,
                "coverage": stage.result.get("coverage", {}),
            }
        except AuditCancelled:
            repository.update(stage_id, status="cancelled", phase="cancelled")
            raise
        except StageCancelled:
            outcome = {"stage_id": stage_id, "status": "cancelled"}
        except Exception as exc:
            repository.update(
                stage_id,
                status="failed",
                error=str(exc)[:1000],
                usage=provider.usage if provider else {},
            )
            outcome = {
                "stage_id": stage_id,
                "status": "failed",
                "error": str(exc)[:1000],
            }
        return {"scout_outcome": outcome}

    def join(self, state):
        run = self.repository.get(state["run_id"])
        static, scout = state["codeql_outcome"], state["scout_outcome"]
        complete = (
            static["status"] == "completed"
            and scout["status"] == "completed"
            and scout.get("coverage", {}).get("status") == "completed"
        )
        dual = {
            "status": "completed" if complete else "partial",
            "codeql": static,
            "scout": scout,
            "scout_stage_id": scout["stage_id"],
            "review_ready": static["status"] == "completed"
            or scout.get("coverage", {}).get("inspected_windows", 0) > 0,
            "meaning": "Branch completion and source coverage are not vulnerability accuracy",
        }
        self.repository.update(
            state["run_id"],
            coverage={**run.coverage, "dual_engine": dual},
            status="completed" if static["status"] == "completed" else "failed",
            phase="discovery_ready" if complete else "discovery_partial",
            error=static.get("error"),
        )
        return {"joined": True}
