"""Project the shared discovery kernel's scan and scout branches to old Web DTOs."""

from semflow_research.public.baselines import export, findings
from semflow_research.public.runs import inspect, specification
from sqlmodel import select

from app.adapters.artifacts import ArtifactStore
from app.models import get_datetime_utc
from app.persistence.stage_models import StageRun
from app.research_bridge.models import ResearchBinding
from app.research_bridge.projection import project
from app.research_bridge.protocol import verify_receipt
from app.research_bridge.requests import research_root


def project_scan(session, binding, audit, result):
    # WIRE-RECV:research.result — peer: discovery.execute / discovery_merge.
    # AGENT: CodeQL failure is never successful empty findings. Scout remains a
    # separately mapped branch; preserve the original research receipt unchanged.
    result = verify_receipt(binding, audit, result)
    if binding.manifest is not None:
        if binding.manifest != result.manifest.model_dump(mode="json"):
            raise ValueError("Scan projection cannot replace an immutable manifest")
        return audit
    static = result.result.baseline if result.result else None
    if static is not None:
        export(
            static,
            root=research_root(),
            target=ArtifactStore().directory(str(audit.id)),
        )
        audit.findings = findings(
            static,
            root=research_root(),
            legacy_source_digest=binding.legacy_source_digest,
        )
        audit.codeql_version = static.codeql_version
    dual = None
    if binding.scout_stage_id:
        scout_binding = session.exec(
            select(ResearchBinding)
            .where(ResearchBinding.stage_id == binding.scout_stage_id)
            .with_for_update()
        ).one()
        child = inspect(scout_binding.execution_id, root=research_root())
        scout_binding.request = specification(
            scout_binding.execution_id, root=research_root()
        ).model_dump(mode="json")
        scout_binding.resources, scout_binding.legacy_source_digest = (
            binding.resources,
            binding.legacy_source_digest,
        )
        if child is not None:
            # project commits its own idempotent stage transaction. The scan
            # projection can be repeated after a crash without another model call.
            project(session, scout_binding, child, root=research_root())
        scout = session.get(StageRun, binding.scout_stage_id)
        static_branch = (
            next((b for b in result.result.branches if b.branch == "scan"), None)
            if result.result
            else None
        )
        dual = {
            "status": "completed"
            if static is not None
            and scout.status == "completed"
            and scout.result.get("coverage", {}).get("status") == "completed"
            else "partial",
            "codeql": {"status": static_branch.status if static_branch else "failed"},
            "scout": {
                "stage_id": str(scout.id),
                "status": scout.status,
                "coverage": scout.result.get("coverage", {}),
            },
            "scout_stage_id": str(scout.id),
            "review_ready": static is not None
            or scout.result.get("coverage", {}).get("inspected_windows", 0) > 0,
            "meaning": "Branch completion and source coverage are not vulnerability accuracy",
        }
    if audit.status != "cancelled":
        audit.status = "completed" if static is not None else "failed"
        audit.phase = (
            "discovery_ready"
            if dual and dual["status"] == "completed"
            else "discovery_partial"
            if dual
            else audit.status
        )
        audit.error = result.failure.message if result.failure else None
    audit.coverage = {
        **audit.coverage,
        **({"dual_engine": dual} if dual else {}),
        "research_receipt": {
            "execution_id": str(result.execution_id),
            "manifest": result.manifest.model_dump(mode="json"),
            "source_digest": binding.request["source"]["tree_sha256"],
            "legacy_source_digest": binding.legacy_source_digest,
        },
    }
    audit.updated_at = get_datetime_utc()
    binding.manifest = result.manifest.model_dump(mode="json")
    session.add(audit)
    session.add(binding)
    session.commit()
    session.refresh(audit)
    return audit
