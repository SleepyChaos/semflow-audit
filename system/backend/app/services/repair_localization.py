"""Chinese display text is derived; saved patch content and verdicts never change."""

import copy
import re

from sqlmodel import select

from app.persistence.stage_models import RepairRecord, StageRun
from app.services.context_materials import digest


def fields(record):
    return [
        {
            "key": digest([record["id"], index, change["reason"]]),
            "path": ["changes", index, "reason"],
            "text": change["reason"],
        }
        for index, change in enumerate(record["changes"])
        if re.search(r"[A-Za-z]{3,}", change["reason"])
        and not re.search(r"[\u4e00-\u9fff]", change["reason"])
    ]


def translation_jobs(audit_id, session):
    return session.exec(
        select(StageRun)
        .where(StageRun.audit_id == audit_id, StageRun.kind == "candidate_translation")
        .order_by(StageRun.created_at)
    ).all()


def localized_repair(record, jobs):
    result = copy.deepcopy(record)
    translations = {}
    for job in jobs:
        translations.update(job.result.get("translations", {}))
    missing = []
    for field in fields(record):
        if text := translations.get(field["key"]):
            result["changes"][field["path"][1]]["reason"] = text
        else:
            missing.append(field)
    result["needs_localization"] = bool(missing)
    result["localization_pending"] = bool(missing) and any(
        job.status in {"queued", "running"} for job in jobs
    )
    return result


def localization_inputs(audit, session):
    jobs = translation_jobs(audit.id, session)
    records = session.exec(
        select(RepairRecord).where(RepairRecord.audit_id == audit.id)
    ).all()
    pending = []
    for record in records:
        raw = record.model_dump(mode="json")
        localized = localized_repair(raw, jobs)
        pending.extend(fields(localized))
    return {"fields": pending, "snapshot_hash": audit.snapshot_hash}
