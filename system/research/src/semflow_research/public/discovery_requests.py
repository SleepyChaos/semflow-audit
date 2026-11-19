"""Mechanical discovery request assembly shared by CLI experiments and Web adapters."""

import hashlib
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field
from semflow_contracts.bundles import CandidateBundle, EvidenceBundle
from semflow_contracts.common import Contract, SourceSnapshot
from semflow_contracts.discovery import (
    DiscoverInput,
    QueryPack,
    QuerySuite,
    ReviewInput,
    ReviewPolicy,
    ScanInput,
    ScoutInput,
    WindowPolicy,
)
from semflow_contracts.errors import ResearchError
from semflow_contracts.runs import ExecutionPolicy, ModelProfile, validate_spec
from semflow_contracts.security_specifications import SecuritySpecificationPolicy

from semflow_research.adapters.snapshot import snapshot_digest
from semflow_research.public.baselines import for_execution as baseline_for
from semflow_research.public.implementation import code_digest
from semflow_research.public.runs import capture_source, inspect, specification
from semflow_research.runtime.artifacts import LocalArtifacts
from semflow_research.runtime.bundle_reader import read_bundle
from semflow_research.runtime.ledger import input_artifacts


class DiscoveryOptions(Contract):
    operation: Literal["scan", "scout", "review", "discover"]
    language: Literal["python", "javascript"] = "python"
    model: ModelProfile | None = None
    policy: ExecutionPolicy
    query_pack: str = Field(
        min_length=3, description="Installed CodeQL pack name@version"
    )
    suite: str = Field(
        min_length=1, description="Query suite path inside the frozen pack"
    )
    build_profile: str = "none"
    supplemental_rules: tuple[dict, ...] = ()
    scope_paths: tuple[str, ...] = ()
    inspection_paths: tuple[str, ...] = ()
    scheduling_profile: Literal["full", "runtime_first"] = "full"
    include_third_party: bool = False
    window_lines: int = Field(default=100, ge=20, le=150)
    max_windows: int = Field(default=1, ge=0)
    max_steps_per_window: int = Field(default=1, ge=1)
    max_branch_calls: int | None = Field(default=1, ge=1)
    batch_size: int = Field(default=2, ge=1)
    max_batches: int = Field(default=1, ge=0)
    supplement_insufficient: bool = False
    evidence_navigation: bool = True
    strict_refutations: bool = False
    max_steps: int = Field(default=1, ge=1)
    max_context_chars: int = Field(default=40000, ge=1)
    required_branches: tuple[Literal["scan", "scout"], ...] = ("scan", "scout")
    scout_method_version: str = "8"
    security_specifications: SecuritySpecificationPolicy | None = None
    review_method_version: str = "12"
    scout_prompt_version: int = 8
    review_prompt_version: int = 12
    # Peer: DiscoverInput.review / runtime.dual_discovery.execute.
    # AGENT: false schedules only scan/scout, leaving review as an explicit later
    # execution; do not run review merely because a method revision is configured.
    run_review: bool = True


def _prompt(root, execution_id, role, version):
    path = Path(__file__).resolve().parents[1] / "prompts" / f"{role}.v{version}.txt"
    if not path.is_file():
        raise ResearchError(
            "unsupported_version", f"Missing frozen {role} Prompt version {version}"
        )
    ref = LocalArtifacts(root / "artifacts", execution_id).commit(
        path.read_bytes(),
        kind="prompt",
        schema_version="prompt/1",
        media_type="text/plain",
    )
    return {
        "role": role,
        "template_id": role,
        "version": str(version),
        "content": ref.model_dump(mode="json"),
        "sha256": ref.sha256,
    }


def _source(root, options, execution_id, source_directory, upstream_execution_id):
    if source_directory is not None:
        return capture_source(
            source_directory,
            root=root,
            owner_execution_id=execution_id,
            languages=(options.language,),
        )
    if upstream_execution_id is None:
        raise ResearchError(
            "invalid_contract",
            "Discovery needs a source directory or upstream execution",
        )
    upstream = specification(upstream_execution_id, root=root)
    if upstream.module != "discovery" or upstream.source is None:
        raise ResearchError(
            "invalid_contract", "Upstream execution is not a discovery source"
        )
    return upstream.source


def _scan_inputs(options, resources):
    try:
        pack_name, pack_version = options.query_pack.split("@", 1)
    except ValueError as exc:
        raise ResearchError(
            "invalid_contract", "query_pack must be name@version"
        ) from exc
    pack = resources.CODEQL_PACK_PATH / pack_name / pack_version
    suite = pack / options.suite
    if not suite.is_file():
        raise ResearchError("tool_unavailable", "Frozen query suite is missing")
    return ScanInput(
        query_pack=QueryPack(
            name=pack_name, version=pack_version, digest=snapshot_digest(pack)
        ),
        suite=QuerySuite(
            name=options.suite, digest=hashlib.sha256(suite.read_bytes()).hexdigest()
        ),
        supplemental_rules=tuple(options.supplemental_rules),
        build_profile=options.build_profile,
    )


def _scout_inputs(options):
    return ScoutInput(
        scope_paths=options.scope_paths,
        security_specifications=options.security_specifications,
        inspection_paths=options.inspection_paths,
        scheduling_profile=options.scheduling_profile,
        include_third_party=options.include_third_party,
        window_lines=options.window_lines,
        window_policy=WindowPolicy(
            version="1",
            max_windows=options.max_windows,
            max_steps_per_window=options.max_steps_per_window,
            max_calls=options.max_branch_calls,
        ),
    )


def _review_policy(options):
    navigated = options.evidence_navigation and options.review_method_version == "12"
    if options.strict_refutations and not navigated:
        raise ResearchError(
            "invalid_contract",
            "Independent refutations require navigated review method 12",
        )
    return ReviewPolicy(
        version=("4" if options.strict_refutations else "3") if navigated else "1",
        batch_size=options.batch_size,
        max_batches=options.max_batches,
        supplement_insufficient=options.supplement_insufficient,
        max_steps=options.max_steps,
        max_context_chars=options.max_context_chars,
        scope_paths=options.scope_paths,
    )


def assemble_discovery(
    *,
    root: Path,
    options: DiscoveryOptions,
    resources,
    dependency_lock: Path,
    source_directory: Path | None = None,
    source_snapshot: SourceSnapshot | None = None,
    upstream_execution_id: UUID | None = None,
    execution_id: UUID | None = None,
):
    execution_id = execution_id or uuid4()
    if source_snapshot is not None and (
        source_directory is not None or upstream_execution_id is not None
    ):
        raise ResearchError(
            "invalid_contract", "Choose exactly one source snapshot input"
        )
    source = source_snapshot or _source(
        root, options, execution_id, source_directory, upstream_execution_id
    )
    scan = (
        _scan_inputs(options, resources)
        if options.operation in {"scan", "discover"}
        else None
    )
    prompts = []
    if options.operation in {"scout", "discover"}:
        prompts.append(
            _prompt(root, execution_id, "scout", options.scout_prompt_version)
        )
    if options.operation in {"review"} or (
        options.operation == "discover" and options.run_review
    ):
        prompts.append(
            _prompt(root, execution_id, "review", options.review_prompt_version)
        )
    model = options.model if options.operation != "scan" else None
    if options.operation == "scan":
        inputs = scan
    elif options.operation == "scout":
        inputs = _scout_inputs(options)
    elif options.operation == "review":
        if upstream_execution_id is None:
            raise ResearchError(
                "invalid_contract", "Review needs a published upstream discovery result"
            )
        previous = inspect(upstream_execution_id, root=root)
        if (
            previous is None
            or previous.result is None
            or not previous.result.candidates
            or not previous.result.evidence
        ):
            raise ResearchError(
                "invalid_contract", "Review needs frozen candidate and evidence bundles"
            )
        artifacts = LocalArtifacts(
            root / "artifacts",
            execution_id,
            upstream=input_artifacts(previous),
        )
        producers = set()
        for reference, schema in (
            (previous.result.candidates, CandidateBundle),
            (previous.result.evidence, EvidenceBundle),
        ):
            artifacts, loaded = read_bundle(
                artifacts, source.snapshot_id, reference, schema
            )
            producers.update(loaded.producers)
        # Interface peer: bundle_io.import_targets checks verified leaf producers.
        # AGENT: a coordinator owns an index, not its members. Preserve original
        # owners across nested indexes and empty bundles; review the receiver too.
        inputs = ReviewInput(
            targets=previous.result.candidates,
            evidence=previous.result.evidence,
            source_execution_ids=tuple(sorted(producers, key=str)),
            baseline=baseline_for(upstream_execution_id, root=root),
            policy=_review_policy(options),
        )
    else:
        inputs = DiscoverInput(
            scan=scan,
            scout=_scout_inputs(options),
            review=_review_policy(options) if options.run_review else None,
            required_branches=options.required_branches,
            scout_method_version=options.scout_method_version,
            review_method_version=options.review_method_version,
        )
    return validate_spec(
        {
            "execution_id": str(execution_id),
            "module": "discovery",
            "operation": options.operation,
            "lineage": {"parent_execution_id": None},
            "source": source.model_dump(mode="json"),
            "language": options.language,
            "implementation": {
                "method_id": "semflow.discovery." + options.operation,
                "method_version": "1"
                if options.operation == "discover"
                else options.scout_method_version
                if options.operation == "scout"
                else options.review_method_version
                if options.operation == "review"
                else "1",
                "code_digest": code_digest(),
                # Peer: discovery_commands.dispatch. AGENT: the caller supplies
                # exact lock bytes; wheel locations never imply a repository.
                "dependency_lock_digest": hashlib.sha256(
                    dependency_lock.read_bytes()
                ).hexdigest(),
            },
            "prompts": prompts,
            "model": model.model_dump(mode="json") if model else None,
            "policy": options.policy.model_dump(mode="json"),
            "inputs": inputs.model_dump(mode="json"),
        }
    )
