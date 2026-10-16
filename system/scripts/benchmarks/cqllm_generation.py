"""Paired metadata-only rule synthesis using actual platform core adapters."""

import json
import re
from hashlib import sha256
from uuid import UUID

from app.adapters.ai.policy import CallBudget, policy_snapshot
from app.adapters.ai.provider import CompatibleModel
from app.adapters.codeql.custom import compile_query, fixed_dependencies, prepare_query
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.retrieval.dual_corpus import retrieve_both
from app.core.db import engine
from app.persistence.knowledge_models import KnowledgeChunk
from pydantic import BaseModel, ConfigDict, Field
from scripts.benchmarks.cqllm_materials import REPO
from scripts.benchmarks.mechanical_pipeline import save
from sqlmodel import Session, select


class QueryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=40, max_length=60000)
    modules: dict[str, str] = Field(default_factory=dict, max_length=12)


def corpus_identity():
    with Session(engine) as db:
        rows = db.exec(
            select(KnowledgeChunk).where(KnowledgeChunk.owner_id.is_(None))
        ).all()
        return sha256(
            json.dumps(
                sorted(
                    [r.model_dump(mode="json", exclude={"embedding"}) for r in rows],
                    key=lambda r: r["id"],
                ),
                sort_keys=True,
            ).encode()
        ).hexdigest()


def configuration(version="1"):
    if version not in {"1", "2"}:
        raise ValueError("Unknown CQLLM prompt version")
    prompt = (REPO / f"benchmarks/prompts/cqllm-rule.v{version}.txt").read_text()
    policy = policy_snapshot("rule")
    policy.update(max_calls=4, max_tokens=0, max_seconds=0)
    return {
        "policy": policy,
        "prompt": prompt,
        "prompt_version": f"cqllm-{version}",
        "prompt_sha256": sha256(prompt.encode()).hexdigest(),
        "dependencies": fixed_dependencies("python"),
        "corpus_identity": corpus_identity(),
        "retrieval_mode": "bm25",
        "compiler_attempts": 2,
        "model_tasks": 596,
        "no_hidden_execution_feedback": True,
        "codeql_cli": CodeQLScanner().version(),
    }


def output_contract(task):
    identity = task["id"]
    if not re.fullmatch(r"row-[0-9]{4}", identity):
        raise ValueError("Invalid frozen row identity")
    generated_id = f"audit/cqllm-{identity}"
    # No requirement text enters the header: descriptions may contain */ or tags.
    return {
        "generated_id": generated_id,
        "kind": "problem",
        "query_header": (
            "/**\n * @name Generated security detector\n"
            " * @description Detects the vulnerability defined in the supplied requirement.\n"
            " * @kind problem\n * @problem.severity warning\n"
            f" * @precision medium\n * @id {generated_id}\n */\n"
        ),
        "select_contract": "location-bearing entity, message string",
    }


def provider(directory, config):
    model = CompatibleModel()
    model.policy = config["policy"]
    model.budget = CallBudget(model.policy, model.records)
    model.prompt_version = config["prompt_version"]
    model.prompt_snapshot = {
        "purpose": "rule",
        "version": config["prompt_version"],
        "content": config["prompt"],
        "sha256": config["prompt_sha256"],
    }
    model.response_directory = directory
    model.persist = lambda: save(
        directory / "model-calls.json",
        {
            "usage": model.usage,
            "records": model.records,
        },
    )
    return model


def generate(task, arm, root, config):
    directory = root / "arms" / arm / task["id"]
    final = directory / "result.json"
    if final.exists():
        return json.loads(final.read_text())
    if (directory / "started.json").exists():
        raise RuntimeError(
            f"Uncommitted model task requires explicit recovery: {arm}/{task['id']}"
        )
    directory.mkdir(parents=True, exist_ok=True)
    result = {
        "task_id": task["id"],
        "arm": arm,
        "status": "retrieval_failed",
        "semantic_correct": None,
    }
    knowledge = []
    if arm == "current_rag":
        requirement = task["requirement"]
        try:
            knowledge = retrieve_both(
                UUID("00000000-0000-0000-0000-000000000001"),
                "python",
                " ".join(requirement.values()),
                config["dependencies"]["codeql/python-all"]["version"],
                mode=config["retrieval_mode"],
                enhanced=True,
                exact_cwe=True,
            )
        except Exception as error:  # noqa: BLE001 - durable benchmark boundary
            result["error"] = str(error)
            save(final, result)
            return result
    save(directory / "retrieval.json", knowledge)
    model = provider(directory, config)
    payload = {
        "requirement": task["requirement"],
        "dependencies": config["dependencies"],
        "knowledge": knowledge,
    }
    if config.get("prompt_version") == "cqllm-2":
        payload["output_contract"] = output_contract(task)
    save(directory / "started.json", {"task": task, "arm": arm})
    try:
        for attempt in range(1, config["compiler_attempts"] + 1):
            path = directory / f"attempt-{attempt}"
            path.mkdir(exist_ok=True)
            save(path / "input.json", payload)
            output = model.generate("rule", payload, QueryOutput)
            save(path / "generation.json", output.model_dump())
            result.update(status="compile_failed", generated=True, attempt=attempt)
            try:
                prepare_query(
                    path, "python", output.query, output.modules, config["dependencies"]
                )
                compile_query(path, path / "compile.log")
                result.update(status="compiled", pack=str(path), compile_success=True)
                break
            except Exception as error:  # noqa: BLE001 - same bounded feedback in both arms
                feedback = (
                    (path / "compile.log").read_text()[-12000:]
                    if (path / "compile.log").exists()
                    else str(error)
                )
                save(
                    path / "compile-result.json",
                    {"status": "failed", "error": str(error)},
                )
                result["error"] = str(error)
                result.setdefault("first_compile_success", False)
                payload = {
                    **payload,
                    "previous_query": output.model_dump(),
                    "compiler_feedback": feedback,
                }
        result.setdefault("first_compile_success", result.get("compile_success", False))
    except Exception as error:  # noqa: BLE001 - retain provider/validation failures
        result.update(status="generation_failed", error=str(error))
    result.update(usage=model.usage, model_calls=model.records)
    result["provider_interrupted"] = bool(model.records) and model.records[-1].get(
        "error_code"
    ) in {"timeout", "provider_error", "rate_limited"}
    save(final, result)
    print(arm, task["id"], result["status"], flush=True)
    return result
