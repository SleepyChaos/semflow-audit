"""Mechanical local assembly of the existing frozen rule request contract."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from uuid import UUID, uuid4, uuid5

from pydantic import Field
from semflow_contracts.common import Contract, digest
from semflow_contracts.corpus import CorpusDocument
from semflow_contracts.errors import ResearchError
from semflow_contracts.rules import RetrievalPolicy, RuleMethodPolicy
from semflow_contracts.runs import (
    ExecutionPolicy,
    ModelProfile,
    PromptSnapshot,
    RuleGenerateSpec,
)

from semflow_research.public.configuration import load_resources
from semflow_research.public.corpus import embedding_for_documents, freeze
from semflow_research.public.holdouts import select as select_holdout
from semflow_research.public.implementation import code_digest
from semflow_research.public.runs import capture_source, inspect, specification
from semflow_research.public.targets import select_targets
from semflow_research.public.toolchains import capture
from semflow_research.runtime.artifacts import LocalArtifacts


class LocalDocument(Contract):
    collection: Literal["reference", "rule_example"]
    title: str
    source: str
    language: Literal["python", "javascript", "any"]
    chunks: tuple[str, ...] = Field(min_length=1)
    provenance: dict
    document_id: UUID | None = None
    version: str | None = None
    created_at: datetime | None = None
    vectors: tuple[tuple[float, ...] | None, ...] | None = None


class LocalDevelopment(Contract):
    compile: bool = True
    project_replay: bool = False


class LocalAcceptance(Contract):
    fixture_validation: bool = True
    holdout_id: str | None = None


class RuleOptions(Contract):
    # Peer: assemble_rule -> RuleGenerateInput / rule_operations.prepare_inputs.
    # AGENT: these are scientific choices, not a second algorithm. False flags,
    # absent holdouts and selected baseline must retain the same core semantics.
    requirement: str = Field(min_length=10, max_length=5000)
    language: Literal["python", "javascript"] = "python"
    purpose: Literal["review_anchor", "vulnerability_detector", "framework_model"] = (
        "vulnerability_detector"
    )
    strategy: Literal["auto", "model", "extend", "new_query"] = "auto"
    source_paths: tuple[str, ...] = ()
    model: ModelProfile
    policy: ExecutionPolicy
    retrieval: RetrievalPolicy
    generation: RuleMethodPolicy
    development: LocalDevelopment
    acceptance: LocalAcceptance
    prompt_version: int = Field(default=8, ge=1)


def resources_for(path, options, *, root):
    return load_resources(
        path,
        SimpleNamespace(model=options.model, policy=options.policy, inputs=None),
        root=root,
    )


def documents_for(documents, execution_id):
    captured = datetime.now(UTC)
    result = []
    for value in documents:
        doc = LocalDocument.model_validate(value)
        identifier = doc.document_id or uuid5(
            execution_id, "corpus/" + doc.collection + "/" + doc.source
        )
        version = doc.version or digest(
            {"chunks": doc.chunks, "provenance": doc.provenance}
        )
        result.append(
            CorpusDocument(
                **doc.model_dump(exclude={"document_id", "version", "created_at"}),
                document_id=identifier,
                version=version,
                created_at=doc.created_at or captured,
            )
        )
    return tuple(result)


def assemble_rule(
    *,
    root: Path,
    documents,
    options: RuleOptions,
    resources,
    dependency_lock: Path,
    source_directory: Path | None = None,
    upstream_execution_id: UUID | None = None,
    candidate_ids: tuple[UUID, ...] = (),
    actor=None,
    confirmation_reason=None,
    execution_id: UUID | None = None,
) -> RuleGenerateSpec:
    execution_id = execution_id or uuid4()
    artifacts = LocalArtifacts(root / "artifacts", execution_id)
    target, baseline = None, None
    if upstream_execution_id:
        upstream = specification(upstream_execution_id, root=root)
        previous = inspect(upstream_execution_id, root=root)
        if (
            previous is None
            or previous.module != "discovery"
            or previous.result is None
        ):
            raise ResearchError(
                "invalid_contract", "Rule input needs a published discovery result"
            )
        source = upstream.source
        from semflow_research.public.baselines import for_execution

        baseline = for_execution(upstream_execution_id, root=root)
        if candidate_ids:
            if len(candidate_ids) != 1 or not actor or not confirmation_reason:
                raise ResearchError(
                    "invalid_contract",
                    "Rule target selection requires one candidate and explicit human confirmation",
                )
            source, target = select_targets(
                root=root,
                upstream_execution_id=upstream_execution_id,
                execution_id=execution_id,
                candidate_ids=candidate_ids,
                actor=actor,
                confirmation_reason=confirmation_reason,
            )
    elif source_directory is not None:
        source = capture_source(
            source_directory,
            root=root,
            owner_execution_id=execution_id,
            languages=(options.language,),
        )
    else:
        raise ResearchError(
            "invalid_contract", "Select a source directory or upstream discovery result"
        )
    if options.language not in source.languages:
        raise ResearchError(
            "identity_mismatch", "Rule language differs from its frozen source"
        )
    if options.development.project_replay and baseline is None:
        raise ResearchError(
            "invalid_contract",
            "Project replay requires the original upstream scan baseline",
        )
    documents = documents_for(documents, execution_id)
    corpus = freeze(
        documents,
        root=root,
        owner_execution_id=execution_id,
        embedding=embedding_for_documents(documents, resources)
        if options.retrieval.mode != "bm25" or any(doc.vectors for doc in documents)
        else None,
    )
    toolchain = capture(
        root=root,
        owner_execution_id=execution_id,
        language=options.language,
        settings=resources,
    )
    prompt_path = (
        Path(__file__).resolve().parents[1]
        / f"prompts/rule.v{options.prompt_version}.txt"
    )
    if not prompt_path.is_file():
        raise ResearchError(
            "unsupported_version", "Selected rule Prompt version is unavailable"
        )
    prompt_ref = artifacts.commit(
        prompt_path.read_bytes(), kind="prompt", schema_version="prompt/1"
    )
    prompt = PromptSnapshot(
        role="rule",
        template_id="rule",
        version=str(options.prompt_version),
        content=prompt_ref,
        sha256=prompt_ref.sha256,
    )
    # WIRE-SEND:research.run — peer: rule_operations.prepare_inputs / typed RuleGenerateSpec.
    # AGENT: CLI IDs/Prompt/toolchain are mechanical; never replace caller method
    # flags, send holdout fixtures to RAG, or omit requested original-project replay.
    return RuleGenerateSpec.model_validate(
        {
            "execution_id": str(execution_id),
            "module": "rules",
            "operation": "generate",
            "lineage": {},
            "source": source.model_dump(mode="json"),
            "language": options.language,
            "implementation": {
                "method_id": "semflow.rules.rag",
                "method_version": "8",
                "code_digest": code_digest(),
                "dependency_lock_digest": hashlib.sha256(
                    dependency_lock.read_bytes()
                ).hexdigest(),
            },
            "prompts": [prompt.model_dump(mode="json")],
            "model": options.model.model_dump(mode="json"),
            "policy": options.policy.model_dump(mode="json"),
            "inputs": {
                "purpose": options.purpose,
                "requirement": options.requirement,
                "target": target,
                "source_paths": options.source_paths,
                "strategy": options.strategy,
                "corpus": corpus.model_dump(mode="json"),
                "retrieval": options.retrieval.model_dump(mode="json"),
                "generation": options.generation.model_dump(mode="json"),
                "development": {
                    **options.development.model_dump(mode="json"),
                    "static_baseline": baseline.model_dump(mode="json")
                    if baseline
                    else None,
                    "query_pack": toolchain.model_dump(mode="json"),
                },
                "acceptance": {
                    "fixture_validation": options.acceptance.fixture_validation,
                    "holdout": select_holdout(options.acceptance.holdout_id).model_dump(
                        mode="json"
                    )
                    if options.acceptance.holdout_id
                    else None,
                },
            },
        }
    )
