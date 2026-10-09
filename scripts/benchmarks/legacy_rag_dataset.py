"""Freeze the original six-task evaluation and old retrieval inputs before IO."""

import copy
import hashlib
import json
import shutil
from pathlib import Path
from uuid import uuid4

from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.snapshot import snapshot_digest
from app.core.db import engine
from app.domain.audit import AuditError
from app.models import User
from app.persistence.knowledge_models import KnowledgeChunk
from app.services.context_materials import digest, save_json
from app.services.rule_holdouts import dataset
from sqlmodel import Session, select

from scripts.benchmarks import live_model
from scripts.benchmarks.rule_ablation_oracles import build_databases, variant_dataset

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7"
DEV = (
    ROOT
    / "artifacts/benchmarks/dev-feedback-ablation-6c579229-399b-44a5-829d-055bcaf650d7"
)


def freeze(output, rounds):
    if rounds != 3:
        raise AuditError(
            "This matched protocol requires exactly the original three rounds"
        )
    historical = json.loads((MAIN / "report.json").read_text())
    supplementary = json.loads((DEV / "report.json").read_text())
    rows = [r for r in supplementary["records"] if r["arm"] == "K_spec_routed_dev"]
    if len(rows) != 18:
        raise AuditError("Original K group must contain eighteen complete records")
    cases = historical["manifest"]["cases"]
    hidden = {}
    for case in cases:
        name = case["id"]
        saved = json.loads((MAIN / "holdouts" / name / "dataset.json").read_text())
        if case["hash"] != dataset(name)["hash"] or saved != variant_dataset(name):
            raise AuditError(
                "Original evaluation fixtures changed; do not replace labels"
            )
        hidden[name] = saved
    policy = copy.deepcopy(rows[0]["stage"]["model_config_snapshot"])
    policy.pop("rule_experiment", None)
    policy.pop("prompt_snapshot", None)
    version3 = ROOT / "backend/app/prompts/rule.v3.txt"
    if (
        hashlib.sha256(version3.read_bytes()).hexdigest()
        != historical["manifest"]["expected_prompt_hash"]
    ):
        raise AuditError("Original v3 prompt identity no longer matches")
    with Session(engine) as db:
        corpus = db.exec(
            select(KnowledgeChunk).where(KnowledgeChunk.owner_id.is_(None))
        ).all()
    frozen = []
    for chunk in corpus:
        value = chunk.model_dump(mode="json", exclude={"embedding"})
        value["embedding_hash"] = (
            digest([float(v) for v in chunk.embedding])
            if chunk.embedding is not None
            else None
        )
        frozen.append(value)
    frozen.sort(key=lambda c: c["id"])
    owner = uuid4()
    with Session(engine) as db:
        db.add(
            User(
                id=owner,
                email=f"legacy-rag-{owner}@research.invalid",
                hashed_password="disabled-research-owner",
                is_active=False,
            )
        )
        db.commit()
    save_json(output / "new-corpus.json", frozen)
    save_json(output / "old-records.json", rows)
    save_json(output / "hidden-manifest.json", hidden)
    save_json(
        output / "old-corpus.json", json.loads((MAIN / "corpus.json").read_text())
    )
    manifest = {
        "owner": str(owner),
        "cases": cases,
        "rounds": rounds,
        "workers": 2,
        "seed": 20261004,
        "policy": policy,
        "cli": CodeQLScanner().version(),
        "new_corpus_hash": digest(frozen),
        "old_records_hash": digest(rows),
        "hidden_manifest_hash": digest(hidden),
        "corpus_document_ids": sorted({c["document_id"] for c in frozen}),
        "old_corpus_hash": historical["manifest"]["corpus_hash"],
        "historical_main": str(MAIN),
        "historical_dev": str(DEV),
        "arms": {
            "old_K": "v3 specification + official template + frozen old routed retrieval + development feedback",
            "new_v6": "v6 deployed dual corpus, auto retrieval, source inspection, free QL and development/project validation",
        },
        "input_note": "Same requirements, per-task development source and baseline. Old does not read source; new reads one canonical public development handler. Renamed/offset hidden variants and labels never enter either generator.",
        "comparison_note": "Whole-pipeline comparison, not isolated embedding/RAG causality. Historical K score is supplementary; fresh old/new pairs use the same current CLI and per-task audit.",
        "prompt_hashes": {
            v: hashlib.sha256(
                (ROOT / f"backend/app/prompts/rule.v{v}.txt").read_bytes()
            ).hexdigest()
            for v in ("3", "6")
        },
        "audits": {},
        "new_retrieval_mode": "auto",
    }
    save_json(output / "manifest.json", manifest)
    return manifest


def reference_manifest(output, reference):
    """Reuse every completed old-control request without generating it again."""
    manifest = json.loads((reference / "manifest.json").read_text())
    verify_frozen(reference, manifest)
    controls = []
    for path in (reference / "records").glob("*.json"):
        row = json.loads(path.read_text())
        if row["arm"] == "old_K":
            controls.append((path, row))
    if len(controls) != 18:
        raise AuditError("Reference must have all eighteen completed old controls")
    for name in (
        "new-corpus.json",
        "old-corpus.json",
        "old-records.json",
        "hidden-manifest.json",
    ):
        shutil.copyfile(reference / name, output / name)
    for path, row in controls:
        row["reference_record"] = str(path.resolve())
        save_json(output / "records" / path.name, row)
    manifest["new_retrieval_mode"] = "auto"
    manifest["arms"]["new_v6"] = (
        "Actual deployed v6 auto retrieval; same frozen corpus, sources, policy and hidden data"
    )
    manifest["reference_run"] = str(reference.resolve())
    manifest["reference_note"] = (
        "All 18 unchanged old controls reused. New auto requests are fresh; do not combine the strict-hybrid pilot with this group. Sequential groups/caches limit timing inference."
    )
    save_json(output / "manifest.json", manifest)
    return manifest


def prepare_case(output, manifest, case):
    name = case["id"]
    hidden = json.loads((output / "hidden-manifest.json").read_text())[name]
    # Validate cached fixture hashes before reusing the original real databases.
    directory = MAIN / "holdouts" / name
    for kind in ("positive", "negative"):
        expected = hidden["fixtures"][kind]["files"]
        actual = {
            p.relative_to(directory / kind).as_posix(): p.read_text()
            for p in (directory / kind).rglob("*")
            if p.is_file()
        }
        if actual != expected:
            raise AuditError("Original hidden source directory was modified")
    build_databases(directory, hidden)
    source = output / "development-source" / name
    source.mkdir(parents=True, exist_ok=True)
    canonical = dataset(name)["fixtures"]["positive"]["files"]
    body = (
        next(iter(canonical.values()))
        .replace(" # target", "")
        .replace(" // target", "")
    )
    extension = "py" if case["language"] == "python" else "js"
    path = f"app.{extension}"
    (source / path).write_text(body)
    (source / "README.md").write_text(
        "# Development request handler\nA small request handler receives external values and returns or processes them. See the actual implementation for its behavior.\n"
    )
    live_model.OUTPUT = output
    from uuid import UUID

    audit_id, seconds = live_model.new_audit(
        UUID(manifest["owner"]), source, name, case["language"]
    )
    return {
        "id": str(audit_id),
        "source_paths": [path],
        "source_hash": snapshot_digest(source),
        "baseline_seconds": seconds,
        "hidden_hash": hidden["hash"],
    }


def historical_row(output, name, number):
    rows = json.loads((output / "old-records.json").read_text())
    return next(r for r in rows if r["case"] == name and r["round"] == number)


def verify_frozen(output, manifest):
    if (
        digest(json.loads((output / "new-corpus.json").read_text()))
        != manifest["new_corpus_hash"]
    ):
        raise AuditError("Frozen corpus manifest changed")
    frozen = json.loads((output / "new-corpus.json").read_text())
    for filename, key in (
        ("old-records.json", "old_records_hash"),
        ("hidden-manifest.json", "hidden_manifest_hash"),
    ):
        if digest(json.loads((output / filename).read_text())) != manifest[key]:
            raise AuditError("Frozen historical inputs or hidden fixtures changed")
    with Session(engine) as db:
        rows = db.exec(
            select(KnowledgeChunk).where(KnowledgeChunk.owner_id.is_(None))
        ).all()
    by_id = {str(row.id): row for row in rows}
    for saved in frozen:
        row = by_id.get(saved["id"])
        if row is None:
            raise AuditError("Frozen corpus record identity changed")
        current = row.model_dump(mode="json", exclude={"embedding"})
        current["embedding_hash"] = (
            digest([float(v) for v in row.embedding])
            if row.embedding is not None
            else None
        )
        if (
            current != saved
            or hashlib.sha256(row.content.encode()).hexdigest() != row.digest
        ):
            raise AuditError("Frozen corpus record/vector changed")
    for version, expected in manifest["prompt_hashes"].items():
        if (
            hashlib.sha256(
                (ROOT / f"backend/app/prompts/rule.v{version}.txt").read_bytes()
            ).hexdigest()
            != expected
        ):
            raise AuditError("Benchmark prompt changed during execution")
    if CodeQLScanner().version() != manifest["cli"]:
        raise AuditError("CodeQL CLI changed during execution")
