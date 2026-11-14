"""Project a frozen scientific suite into the existing platform test DTO/view."""

from types import SimpleNamespace

from semflow_contracts.common import canonical_bytes
from semflow_research.public.suites import read
from sqlmodel import select

from app.adapters.artifacts import ArtifactStore
from app.adapters.snapshot import snapshot_digest
from app.domain.audit import AuditError
from app.models import get_datetime_utc
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import StageRun
from app.research_bridge.protocol import verify_receipt
from app.research_bridge.repair_inputs import platform_targets
from app.research_bridge.repair_projection import save_view
from app.services.context_materials import digest


def project(session, binding, envelope, *, root):
    stage = session.exec(
        select(StageRun).where(StageRun.id == binding.stage_id).with_for_update()
    ).one()
    audit = session.get(AuditRun, stage.audit_id)
    envelope = verify_receipt(binding, audit, envelope)
    manifest = envelope.manifest.model_dump(mode="json")
    if binding.manifest is not None and binding.manifest != manifest:
        raise AuditError("测试集科研清单已变化", code="integrity_error")
    body = read(envelope.result.suite, root=root)
    definition = body.definition.model_dump(mode="json")
    mapped = platform_targets(
        binding,
        SimpleNamespace(target_refs=body.target_refs),
        stage.inputs["candidate_ids"],
    )
    ids = {
        str(ref.entity_id): value
        for ref, value in zip(body.target_refs, mapped, strict=True)
    }
    for case in definition["cases"]:
        if any(i not in ids for i in case["candidate_ids"]):
            raise AuditError("测试集目标缺少平台身份映射", code="identity_mismatch")
        case["candidate_ids"] = [ids[i] for i in case["candidate_ids"]]
    directory = ArtifactStore().directory(str(stage.id))
    tests = directory / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    for name, text in body.definition.files.items():
        save_view(tests / name, text.encode())
    save_view(tests / "pytest.ini", b"[pytest]\n")
    if body.definition.language == "javascript":
        from semflow_research.public.suites import reporter_bytes

        save_view(tests / "verification-reporter.cjs", reporter_bytes())
    result = {
        "suite": definition,
        "image": body.image_digest,
        "snapshot_hash": audit.snapshot_hash,
        "candidate_ids": sorted(ids[str(r.entity_id)] for r in body.target_refs),
        "origin": "ai_generated",
    }
    result["suite_hash"] = digest(
        {k: result[k] for k in ("suite", "image", "snapshot_hash", "candidate_ids")}
    )
    result["test_files_hash"] = snapshot_digest(tests)
    result["research_suite_ref"] = envelope.result.suite.model_dump(mode="json")
    result["research_receipt"] = {
        "execution_id": str(envelope.execution_id),
        "manifest": manifest,
    }
    # WIRE-RECV:research.repair_suite — peer: public.suites.capture / suite_build.build.
    # AGENT: convert IDs and hash namespaces only in this view; original assertion
    # bytes, public definition/ref and scientific manifest remain unchanged.
    save_view(directory / "suite.json", canonical_bytes(result))
    if binding.manifest is None:
        if stage.status != "cancelled":
            stage.status = envelope.execution_status
        stage.phase = (
            "verification_suite_ready" if stage.status == "completed" else stage.status
        )
        stage.result, stage.usage, stage.updated_at = (
            result,
            envelope.usage.model_dump(mode="json"),
            get_datetime_utc(),
        )
        binding.manifest = manifest
        session.add(stage)
        session.add(binding)
        session.commit()
        session.refresh(stage)
    return stage
