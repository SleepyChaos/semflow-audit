"""Minimal discovery CLI assembly; only research public APIs are imported."""

from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from semflow_contracts.errors import ResearchError
from semflow_research.public.configuration import load_resources
from semflow_research.public.discovery_requests import (
    DiscoveryOptions,
    assemble_discovery,
)
from semflow_research.public.runs import execute

COMMANDS = {
    "discovery-scan",
    "discovery-scout",
    "discovery-review",
    "discovery-discover",
}


def add_parsers(commands):
    for name in sorted(COMMANDS):
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
