"""Actual v8 generation and evaluator-only OWASP condition tests; no auto-publish."""

import argparse
import json
from pathlib import Path
from uuid import UUID

from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.custom import run_query
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.snapshot import snapshot_digest
from app.core.db import engine
from app.domain.audit import ScanPlan
from app.persistence.knowledge_models import RuleVersion
from app.services.rules import RuleService
from sqlmodel import Session, select

from scripts.benchmarks.formal_freeze import OUTPUT, save
from scripts.benchmarks.formal_inputs import GOLD
from scripts.benchmarks.formal_runtime import (
    checkpoint_stage,
    new_stage,
    register_audit,
)
from scripts.benchmarks.formal_scoring import score_cases


class GenerateGraph:
    def __init__(self, service):
        self.service = service

    def invoke(self, state, config):
        s = self.service
        result = s.generate(s.retrieve())
        s.repository.update(
            s.stage_id,
            status="completed",
            phase="benchmark_draft_complete",
            result={
                **s.repository.get(s.stage_id).result,
                "benchmark_rule_id": result["rule_id"],
            },
        )
        return result


def hidden_database(task, configuration):
    source = Path(task["hidden_source"])
    directory = OUTPUT / "rules/hidden" / task["id"]
    receipt = directory / "receipt.json"
    snapshot = snapshot_digest(source)
    if receipt.exists():
        saved = json.loads(receipt.read_text())
        if saved["snapshot"] != snapshot:
            raise RuntimeError("Hidden source changed")
        return directory / "database", snapshot
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / "database").exists():
        raise RuntimeError("Partial hidden database retained; explicit recovery needed")
    pack = configuration["packs"][task["language"]]
    CodeQLScanner().create_database(
        source,
        directory / "database",
        directory / "execution.log",
        ScanPlan(task["language"], pack["pack"], pack["suite"]),
    )
    save(receipt, {"snapshot": snapshot, "input_to_generator": False})
    return directory / "database", snapshot


def evaluate(row, task, config, directory):
    with Session(engine) as db:
        rules = db.exec(
            select(RuleVersion).where(RuleVersion.stage_id == UUID(row["stage_id"]))
        ).all()
        dumped = [r.model_dump(mode="json") for r in rules]
    result = {
        "generation": row,
        "rules": dumped,
        "hidden": {"status": "not_run"},
        "formal_gold": False,
        "scope": "official generated conditions, same language/family; no natural cross-repo generalization",
    }
    if rules:
        rule = rules[0]
        pack = (
            ArtifactStore().directory(row["stage_id"])
            / f"draft-{rule.validation['attempts'] - 1}"
        )
        try:
            database, snapshot = hidden_database(task, config)
            findings = run_query(
                database,
                pack,
                directory / "hidden.sarif",
                directory / "hidden-execution.log",
                snapshot,
            )
            metrics = score_cases(task["hidden_labels"], findings)
            result["hidden"] = {
                "status": "evaluated",
                "metrics": metrics,
                "findings": findings,
                "source_snapshot": snapshot,
                "all_conditions_pass": metrics["counts"]
                == {"TP": 2, "FP": 0, "TN": 2, "FN": 0},
            }
        except Exception as exc:  # noqa: BLE001 - persist failure at benchmark boundary
            result["hidden"] = {
                "status": "infra_failure",
                "error_type": type(exc).__name__,
                "error": str(exc)[:600],
            }
    else:
        result["hidden"]["reason"] = "no_generated_compiled_rule"
    save(directory / "scored.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--tasks", nargs="*")
    args = parser.parse_args()
    tasks = json.loads((GOLD / "rule-tasks.json").read_text())
    config = json.loads((OUTPUT / "config.json").read_text())
    save(
        OUTPUT / "rules/no-rag-control.json",
        {
            "status": "unsupported_current_product_contract",
            "reason": "RuleResponse.knowledge_ids requires >=1 real knowledge ID. Removing retrieval without changing generator schema cannot form a fair no-RAG causal control.",
            "score": None,
            "model_calls": 0,
        },
    )
    for task in tasks:
        if args.tasks and task["id"] not in args.tasks:
            continue
        audit = register_audit(task["id"])
        for number in range(1, args.rounds + 1):
            modes = (
                ["bm25", "vector", "hybrid"]
                if number % 2
                else ["hybrid", "vector", "bm25"]
            )
            for mode in modes:
                directory = OUTPUT / "rules" / task["id"] / f"{mode}-round-{number}"
                if (directory / "scored.json").exists():
                    continue
                row = checkpoint_stage(
                    directory / "generation.json",
                    lambda audit=audit, task=task, mode=mode: new_stage(
                        audit,
                        "rule",
                        "8",
                        {
                            "source_paths": task["source_paths"],
                            "requirement": task["requirement"],
                            "purpose": "vulnerability_detector",
                            "strategy": "auto",
                        },
                        {
                            "retrieval_mode": mode,
                            "collection_routing": True,
                            "corpus_document_ids": config["corpus_document_ids"],
                        },
                    ),
                    RuleService,
                    GenerateGraph,
                )
                scored = evaluate(row, task, config, directory)
                print(
                    json.dumps(
                        {
                            "task": task["id"],
                            "mode": mode,
                            "round": number,
                            "compiled_rules": len(scored["rules"]),
                            "hidden_status": scored["hidden"]["status"],
                            "all_conditions_pass": scored["hidden"].get(
                                "all_conditions_pass"
                            ),
                        }
                    ),
                    flush=True,
                )


if __name__ == "__main__":
    main()
