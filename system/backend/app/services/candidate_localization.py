"""Derived Chinese views retain original candidate and review execution histories."""

import copy
import re

from sqlmodel import select

from app.adapters.artifacts import ArtifactStore
from app.contracts.candidate_translation import TranslationResponse
from app.domain.audit import AuditError
from app.persistence.stage_models import Candidate, StageRun
from app.persistence.stage_repository import StageRepository
from app.services.candidate_reviews import candidate_review
from app.services.context_materials import digest


def technical_identifier(text):
    return bool(
        re.fullmatch(r"[A-Za-z0-9_./:@-]+", text) and re.search(r"[./:@_-]", text)
    )


def chinese_or_identifier(text, original):
    return bool(re.search(r"[\u4e00-\u9fff]", text)) or (
        text == original and technical_identifier(original)
    )


def recover_translations(audit_id, fields, session):
    wanted = {f["key"]: f["text"] for f in fields}
    recovered, sources = {}, []
    jobs = session.exec(
        select(StageRun)
        .where(StageRun.audit_id == audit_id, StageRun.kind == "candidate_translation")
        .order_by(StageRun.created_at)
    ).all()
    for job in jobs:
        for call in job.model_calls:
            name = call.get("response_artifact", "")
            if not re.fullmatch(r"model-call-\d+\.response\.txt", name):
                continue
            try:
                payload = TranslationResponse.model_validate_json(
                    (ArtifactStore().directory(str(job.id)) / name).read_text()
                )
            except OSError, ValueError:
                continue
            allowed = {f["key"] for f in job.inputs.get("fields", [])}
            keys = [t.key for t in payload.translations]
            if len(keys) != len(set(keys)) or not set(keys) <= allowed:
                continue
            accepted = {
                t.key: t.text
                for t in payload.translations
                if t.key in wanted and chinese_or_identifier(t.text, wanted[t.key])
            }
            recovered.update(accepted)
            if accepted:
                sources.append(
                    {
                        "stage_id": str(job.id),
                        "artifact": name,
                        "sha256": digest(payload.model_dump(mode="json")),
                    }
                )
    return {"translations": recovered, "recovered_responses": sources}


def text_fields(payload):
    paths = [("title",), ("description",)]
    review = payload.get("review") or {}
    paths += [("review", "reason")]
    for name in ("checked_premises", "missing_premises", "runtime_unknowns"):
        paths += [("review", name, index) for index in range(len(review.get(name, [])))]
    detail = review.get("detail") or {}
    paths += [("review", "detail", name) for name in ("title", "description", "impact")]
    example = detail.get("exploitation") or {}
    paths += [("review", "detail", "exploitation", "expected_result")]
    for name in ("prerequisites", "steps"):
        paths += [
            ("review", "detail", "exploitation", name, index)
            for index in range(len(example.get(name, [])))
        ]
    result = []
    for path in paths:
        value = payload
        try:
            for part in path:
                value = value[part]
        except KeyError, TypeError, IndexError:
            continue
        if (
            isinstance(value, str)
            and re.search(r"[A-Za-z]{3,}", value)
            and not re.search(r"[\u4e00-\u9fff]", value)
            and not technical_identifier(value)
        ):
            result.append(
                {
                    "key": digest([payload["id"], path, value]),
                    "path": list(path),
                    "text": value,
                }
            )
    return result


def localized_view(payload, stages):
    result = copy.deepcopy(payload)
    translations = {}
    jobs = sorted(
        (s for s in stages.values() if s.kind == "candidate_translation"),
        key=lambda s: s.created_at,
    )
    for job in jobs:
        if str(job.audit_id) == str(payload["audit_id"]):
            translations.update(job.result.get("translations", {}))
    fields = text_fields(result)
    missing = []
    for field in fields:
        translated = translations.get(field["key"])
        if translated:
            target = result
            for part in field["path"][:-1]:
                target = target[part]
            target[field["path"][-1]] = translated
        else:
            missing.append(field)
    result["needs_localization"] = bool(missing)
    result["localization_pending"] = any(
        s.status in {"queued", "running"} for s in jobs
    )
    result["localization_error"] = (
        jobs[-1].error if jobs and jobs[-1].status == "failed" else None
    )
    return result


def localization_inputs(audit, session):
    stages = session.exec(select(StageRun).where(StageRun.audit_id == audit.id)).all()
    by_stage = {s.id: s for s in stages}
    candidates = session.exec(
        select(Candidate)
        .where(Candidate.audit_id == audit.id)
        .order_by(Candidate.created_at)
    ).all()
    latest = {}
    for candidate in candidates:
        key = candidate.identity_key or str(candidate.id)
        old = latest.get(key)
        if (
            not old
            or by_stage[candidate.stage_id].kind == "review"
            or by_stage[old.stage_id].kind != "review"
        ):
            latest[key] = candidate
    fields = []
    for candidate in latest.values():
        review = candidate_review(candidate, by_stage, audit.snapshot_hash)
        if (
            review
            and review["evaluated"]
            and review["stage_status"] not in {"queued", "running"}
        ):
            from app.services.candidate_classification import apply_model_classification

            if review["status"] in {"supported", "excluded", "pending", "insufficient"}:
                apply_model_classification(candidate, review["status"], session)
                session.add(candidate)
        payload = {**candidate.model_dump(mode="json"), "review": review}
        fields += text_fields(localized_view(payload, by_stage))
    return {"fields": fields, "snapshot_hash": audit.snapshot_hash}


def translate_candidates(stage_id, provider):
    repository = StageRepository()
    stage = repository.get(stage_id)
    remaining = list(stage.inputs["fields"])
    translations = dict(stage.result.get("translations", {}))
    metadata = {
        key: value for key, value in stage.result.items() if key != "translations"
    }
    while remaining:
        batch, size = [], 0
        while remaining and (size + len(remaining[0]["text"]) <= 10000 or not batch):
            field = remaining.pop(0)
            size += len(field["text"])
            if field["key"] not in translations:
                batch.append(field)
        if not batch:
            continue
        repository.active(stage_id)
        response = provider.generate(
            "candidate_translation",
            {"texts": [{"key": f["key"], "text": f["text"]} for f in batch]},
            TranslationResponse,
        )
        expected = {f["key"] for f in batch}
        actual = [t.key for t in response.translations]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise AuditError("中文翻译遗漏或改变了文本标识")
        originals = {f["key"]: f["text"] for f in batch}
        if any(
            not chinese_or_identifier(t.text, originals[t.key])
            for t in response.translations
        ):
            raise AuditError("中文翻译仍包含未翻译的英文说明")
        translations.update({t.key: t.text for t in response.translations})
        repository.update(
            stage_id,
            phase="translate_candidate_text",
            result={**metadata, "translations": translations},
            usage=provider.usage,
        )
    repository.update(
        stage_id,
        status="completed",
        phase="translation_ready",
        result={**metadata, "translations": translations},
        usage=provider.usage,
    )
