"""Freeze non-secret runtime identities and evaluator-side exposure receipts."""

import hashlib
import json
import platform
import subprocess
from collections import Counter
from pathlib import Path

from app.adapters.ai.policy import policy_snapshot
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.retrieval.embedding_identity import embedding_identity
from app.core.audit_config import audit_settings as settings
from app.core.db import engine
from app.persistence.knowledge_models import KnowledgeChunk
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "artifacts/research/formal/20261005-calibration-v1"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))


def freeze():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / "config.json"
    if target.exists():
        print("EXISTING_FREEZE=" + str(target))
        return
    code = {}
    for directory in ("system/backend/app", "system/scripts/benchmarks", "system/tests"):
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and path.suffix in {".py", ".txt"}:
                code[str(path.relative_to(ROOT))] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    for name in ("system/uv.lock", "system/backend/pyproject.toml", "AGENTS.md"):
        path = ROOT / name
        code[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    packs = {}
    for language, pack in (
        ("python", settings.PYTHON_QUERY_PACK),
        ("javascript", settings.JAVASCRIPT_QUERY_PACK),
    ):
        name, version = pack.split("@")
        suite = f"codeql-suites/{language}-code-scanning.qls"
        source = settings.CODEQL_PACK_PATH / name / version / suite
        if not source.is_file():
            raise RuntimeError("Required production query suite missing")
        packs[language] = {
            "pack": pack,
            "suite": suite,
            "suite_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "content_hash": digest(
                {
                    str(p.relative_to(source.parent.parent)): hashlib.sha256(
                        p.read_bytes()
                    ).hexdigest()
                    for p in source.parent.parent.rglob("*")
                    if p.is_file()
                }
            ),
        }
    with Session(engine) as db:
        chunks = db.exec(
            select(KnowledgeChunk).where(KnowledgeChunk.owner_id.is_(None))
        ).all()
        corpus = []
        for chunk in chunks:
            row = chunk.model_dump(mode="json", exclude={"embedding"})
            row["embedding_hash"] = (
                digest([float(v) for v in chunk.embedding])
                if chunk.embedding is not None
                else None
            )
            corpus.append(row)
    corpus.sort(key=lambda row: row["id"])
    save(OUTPUT / "corpus.json", corpus)
    prior = []
    for path in (ROOT / "artifacts/research-materials").glob(
        "phase-two-real-pairs-*/manifest.json"
    ):
        prior.extend(json.loads(path.read_text()).get("records", []))
    corpus_text = json.dumps(corpus).lower()
    pairs = json.loads(
        (ROOT / "benchmarks/raw/project-pairs/manifest.json").read_text()
    )["records"]
    exposure = []
    for pair in pairs:
        repository = pair["repository"].removesuffix(".git").lower()
        overlap = [
            r["case_id"]
            for r in prior
            if r.get("repository", "").removesuffix(".git").lower() == repository
            or r.get("cve") == pair["cve"]
        ]
        exposure.append(
            {
                "case_id": pair["case_id"],
                "old_pilot_matches": overlap,
                "rag_identifier_matches": [
                    s
                    for s in (repository.rsplit("/", 1)[-1], pair["cve"].lower())
                    if s in corpus_text
                ],
                "metadata_seen_by_evaluator": True,
                "formal_model_execution": "not_run",
                "unseen_training_claim": False,
                "status": "calibration_candidate_not_certified_blind",
            }
        )
    save(OUTPUT / "exposure.json", exposure)
    configuration = {
        "experiment_id": OUTPUT.name,
        "stage": "calibration_not_formal_holdout",
        "machine": platform.platform(),
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "implementation_hashes": code,
        "working_tree_content_hash": digest(code),
        "codeql_cli": CodeQLScanner().version(),
        "packs": packs,
        "policy": policy_snapshot(),
        "temperature": 0,
        "seed": None,
        "seed_note": "Provider does not send seed; repetitions are requests, not guaranteed independent random seeds",
        "threads": settings.CODEQL_THREADS,
        "ram_mb": settings.CODEQL_RAM,
        "scan_timeout": settings.SCAN_TIMEOUT,
        "corpus_hash": digest(corpus),
        "corpus_document_ids": sorted({r["document_id"] for r in corpus}),
        "corpus_chunks": len(corpus),
        "corpus_counts": dict(Counter(r["corpus"] for r in corpus)),
        "embedding_identity": embedding_identity(),
        "embedding_model": settings.EMBEDDING_MODEL,
        "prompt_versions": {"scout": "1", "review": "4", "rule": "8", "repair": "2"},
        "response_model_identity": "recorded_per_actual_call",
        "target_services": False,
        "gui_tests": False,
    }
    save(target, configuration)
    print(
        json.dumps(
            {
                k: configuration[k]
                for k in (
                    "experiment_id",
                    "codeql_cli",
                    "packs",
                    "corpus_chunks",
                    "corpus_counts",
                )
            }
        )
    )


if __name__ == "__main__":
    freeze()
