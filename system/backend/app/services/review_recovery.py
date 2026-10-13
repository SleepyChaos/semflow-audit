"""One durable supplemental attempt per unresolved, originally scheduled candidate."""

from app.domain.audit import AuditCancelled
from app.persistence.stage_repository import StageCancelled
from app.services.context_materials import digest, save_json


def recover_unreviewed(service, schedule):
    current = service.repository.get(service.stage_id).result
    reviewed = {
        r["id"]
        for batch in current.get("batches", [])
        for r in batch.get("recommendations", [])
    }
    attempted = set(current.get("recovery_attempted_ids", []))
    unresolved = [
        entry
        for entries in schedule
        for entry in entries
        if entry["candidate_id"] not in reviewed | attempted
    ]
    for entry in unresolved:
        service.repository.active(service.stage_id)
        maximum = getattr(service.provider, "policy", {}).get("max_calls", 24)
        available = (maximum - service.provider.usage.get("calls", 0)) if maximum else 2
        if available < 1:
            break
        identifier = entry["candidate_id"]
        current = service.repository.get(service.stage_id).result
        # Persist before requesting a model response. A restart never expands this allowance.
        service.repository.update(
            service.stage_id,
            result={
                **current,
                "recovery_attempted_ids": [
                    *current.get("recovery_attempted_ids", []),
                    identifier,
                ],
            },
        )
        batch_id = "recovery-" + digest(identifier)[:24]
        try:
            rejections = [
                r
                for b in current.get("batches", [])
                for r in b.get("rejected_assessments", [])
                if r["candidate_id"] == identifier
            ]
            feedback = {
                "candidate_id": identifier,
                "validation_errors": [r["reason"] for r in rejections],
                "instruction": "Correct only the rejected candidate. Preserve target.security_property; cite CURRENT target_source_ids and actual supplied pages. If local facts do not establish this exact condition, return insufficient with its actual missing premise. Do not reinterpret another property as this target.",
            }
            result = service.inspect_batch(
                batch_id, [entry], min(2, available), feedback
            )
            save_json(service.directory / "batches" / batch_id / "result.json", result)
        except StageCancelled, AuditCancelled:
            raise
        except Exception as exc:
            code = getattr(exc, "code", "verification_failed")
            if code in {"identity_error", "integrity_error"}:
                raise
            current = service.repository.get(service.stage_id).result
            service.repository.update(
                service.stage_id,
                result={
                    **current,
                    "batches": [
                        *current.get("batches", []),
                        {
                            "batch_id": batch_id,
                            "status": "incomplete",
                            "reason": str(exc)[:500],
                            "code": code,
                            "candidate_ids": [identifier],
                            "unreviewed_candidate_ids": [identifier],
                        },
                    ],
                },
            )
            if code in {
                "budget_exhausted",
                "timeout",
                "provider_error",
                "rate_limited",
            }:
                break
        from app.adapters.ai.policy import stalled

        current = service.repository.get(service.stage_id).result
        if stalled(current.get("batches", []), getattr(service.provider, "policy", {})):
            service.repository.update(
                service.stage_id, result={**current, "stop_reason": "no_progress"}
            )
            break
