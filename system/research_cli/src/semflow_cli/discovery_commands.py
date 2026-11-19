"""Minimal discovery CLI assembly; only research public APIs are imported."""

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from semflow_contracts.errors import ResearchError
from semflow_research.public.configuration import load_resources
from semflow_research.public.discovery_requests import (
    DiscoveryOptions,
    assemble_discovery,
)
from semflow_research.public.runs import execute

DISCOVERY_OPERATIONS = {
    "discovery-scan",
    "discovery-scout",
    "discovery-review",
    "discovery-discover",
}


COMMANDS = DISCOVERY_OPERATIONS | {
    "discovery-review-continue",
    "discovery-review-report",
    "discovery-freeze-specifications",
}


def add_parsers(commands):
    corpus = commands.add_parser("discovery-freeze-specifications")
    corpus.add_argument("--root", type=Path, required=True)
    corpus.add_argument("--documents", type=Path, required=True)
    continuation = commands.add_parser("discovery-review-continue")
    continuation.add_argument("--root", type=Path, required=True)
    continuation.add_argument("--upstream-execution-id", type=UUID, required=True)
    continuation.add_argument("--candidate-id", type=UUID, required=True)
    continuation.add_argument("--resources", type=Path, required=True)
    continuation.add_argument("--dependency-lock", type=Path, required=True)
    continuation.add_argument("--without-cache", action="store_true")

    report = commands.add_parser("discovery-review-report")
    report.add_argument("--root", type=Path, required=True)
    report.add_argument("--execution-id", type=UUID, required=True)
    report.add_argument("--candidate-id", type=UUID)
    for name in sorted(DISCOVERY_OPERATIONS):
        parser = commands.add_parser(name, help="Run a discovery kernel directly")
        parser.add_argument("--root", type=Path, required=True)
        source = parser.add_mutually_exclusive_group(
            required=name != "discovery-review"
        )
        source.add_argument("--source-directory", type=Path)
        source.add_argument("--upstream-execution-id", type=UUID)
        parser.add_argument("--options", type=Path, required=True)
        parser.add_argument("--resources", type=Path, required=True)
        parser.add_argument("--dependency-lock", type=Path, required=True)


def dispatch(args):
    if args.command == "discovery-freeze-specifications":
        from pydantic import TypeAdapter
        from semflow_contracts.corpus import CorpusDocument
        from semflow_research.public.corpus import freeze

        adapter = TypeAdapter(tuple[CorpusDocument, ...])
        documents = adapter.validate_json(args.documents.read_bytes())
        if (
            not documents
            or len(documents) > 1000
            or any(
                row.provenance.get("source_scope") != "vulinstruct_train"
                or row.collection != "reference"
                or len(row.chunks) != 1
                for row in documents
            )
        ):
            raise ResearchError(
                "invalid_contract",
                "Expected 1–1000 single-statement training references",
            )
        versions = {row.version for row in documents}
        if len(versions) != 1:
            raise ResearchError(
                "invalid_contract", "Freeze one source revision at a time"
            )
        (revision,) = versions
        return freeze(
            documents, root=args.root, owner_execution_id=uuid4(), version=revision
        ).model_dump(mode="json")
    if args.command == "discovery-review-continue":
        from semflow_research.public.review_continuation import assemble

        spec = assemble(
            args.upstream_execution_id,
            args.candidate_id,
            root=args.root,
            reuse_cache=not args.without_cache,
            dependency_lock_digest=sha256(
                args.dependency_lock.read_bytes()
            ).hexdigest(),
        )
        resources = load_resources(args.resources, spec, root=args.root)
        return execute(spec, root=args.root, settings=resources).model_dump(mode="json")
    if args.command == "discovery-review-report":
        from semflow_research.public.discovery_results import read_result
        from semflow_research.public.review_continuation import history

        view = read_result(args.execution_id, root=args.root)
        rows = (
            history(args.execution_id, args.candidate_id, root=args.root)
            if args.candidate_id
            else ()
        )
        return {
            "report": view.review_report.model_dump(mode="json")
            if view.review_report
            else None,
            "cache": view.review_cache.model_dump(mode="json")
            if view.review_cache
            else None,
            "history": [row.model_dump(mode="json") for row in rows],
        }
    options = DiscoveryOptions.model_validate_json(
        args.options.read_bytes()
    ).model_copy(update={"operation": args.command.removeprefix("discovery-")})
    if options.operation == "review" and args.upstream_execution_id is None:
        raise ResearchError(
            "invalid_contract", "Review requires --upstream-execution-id"
        )
    resource_spec = SimpleNamespace(
        policy=options.policy,
        model=None if options.operation == "scan" else options.model,
        inputs=SimpleNamespace(),
    )
    resources = load_resources(args.resources, resource_spec, root=args.root)
    spec = assemble_discovery(
        root=args.root,
        options=options,
        resources=resources,
        dependency_lock=args.dependency_lock,
        source_directory=args.source_directory,
        upstream_execution_id=args.upstream_execution_id,
    )
    # WIRE-SEND:research.run — peer: public.discovery.execute / runtime factory.
    # AGENT: local options become one frozen request; do not add platform IDs or
    # silently change branch/default/scope semantics at this CLI boundary.
    return execute(spec, root=args.root, settings=resources).model_dump(mode="json")
