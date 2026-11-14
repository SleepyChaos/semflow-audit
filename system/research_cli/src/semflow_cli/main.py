"""Independent contract validation and research-ledger inspection commands."""

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError
from semflow_contracts.actions import ControlCommand
from semflow_contracts.common import digest
from semflow_contracts.errors import ResearchError
from semflow_contracts.runs import validate_spec
from semflow_contracts.schemas import SCHEMAS
from semflow_research.public import capabilities
from semflow_research.public.configuration import load_resources
from semflow_research.public.runs import (
    cancel,
    capture_source,
    execute,
    inspect,
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="semflow-research", description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "capabilities", help="Show implemented and planned kernel operations"
    )
    validate = commands.add_parser(
        "validate", help="Validate RunSpec structure, without executing tools"
    )
    validate.add_argument("--spec", type=Path, required=True)
    schema = commands.add_parser("schema", help="Export versioned research JSON Schema")
    schema.add_argument("--kind", choices=list(SCHEMAS), default="run")
    query = commands.add_parser(
        "inspect", help="Read a local result and verify its artifacts"
    )
    query.add_argument("--root", type=Path, required=True)
    query.add_argument("--execution-id", type=UUID, required=True)
    run = commands.add_parser(
        "run", help="Execute a frozen request directly through its research kernel"
    )
    run.add_argument("--spec", type=Path, required=True)
    run.add_argument("--resources", type=Path, required=True)
    run.add_argument("--root", type=Path, required=True)
    for command in ("repair-native", "repair-openhands"):
        hands = commands.add_parser(
            command,
            help="Repair selected upstream candidates; assemble IDs, digests and Prompts locally",
        )
        hands.add_argument("--root", type=Path, required=True)
        hands.add_argument("--upstream-execution-id", type=UUID, required=True)
        hands.add_argument("--candidate-id", type=UUID, action="append", required=True)
        hands.add_argument("--writable", action="append", required=True)
        hands.add_argument("--readable", action="append", default=[])
        hands.add_argument("--max-changed-files", type=int, required=True)
        hands.add_argument("--options", type=Path, required=True)
        hands.add_argument("--resources", type=Path, required=True)
        hands.add_argument("--dependency-lock", type=Path, required=True)
        hands.add_argument(
            "--confirm",
            action="store_true",
            required=True,
            help="Explicitly confirm selected candidates against their frozen source evidence",
        )
        hands.add_argument("--actor", required=True)
        hands.add_argument("--reason", required=True)
    from semflow_cli.discovery_commands import add_parsers as add_discovery_parsers
    from semflow_cli.rule_commands import add_parsers
    from semflow_cli.verification_commands import (
        add_parsers as add_verification_parsers,
    )

    add_discovery_parsers(commands)
    add_parsers(commands)
    add_verification_parsers(commands)
    stop = commands.add_parser(
        "cancel", help="Persist a revision-bound cancellation request"
    )
    cancellation = stop.add_mutually_exclusive_group(required=True)
    cancellation.add_argument("--command-file", type=Path)
    cancellation.add_argument("--execution-id", type=UUID)
    stop.add_argument("--root", type=Path, required=True)
    source = commands.add_parser(
        "capture-source", help="Freeze an explicitly selected source directory"
    )
    source.add_argument("--directory", type=Path, required=True)
    source.add_argument("--root", type=Path, required=True)
    source.add_argument("--owner-execution-id", type=UUID, required=True)
    source.add_argument(
        "--language", action="append", choices=["python", "javascript"], required=True
    )
    return root


def dispatch(args) -> dict:
    from semflow_cli.discovery_commands import COMMANDS as DISCOVERY_COMMANDS
    from semflow_cli.discovery_commands import dispatch as dispatch_discovery
    from semflow_cli.rule_commands import COMMANDS
    from semflow_cli.rule_commands import dispatch as dispatch_rule
    from semflow_cli.verification_commands import COMMANDS as VERIFICATION_COMMANDS
    from semflow_cli.verification_commands import dispatch as dispatch_verification

    if args.command in DISCOVERY_COMMANDS:
        return dispatch_discovery(args)
    if args.command in COMMANDS:
        return dispatch_rule(args)
    if args.command in VERIFICATION_COMMANDS:
        return dispatch_verification(args)
    if args.command in {"repair-native", "repair-openhands"}:
        from semflow_research.public.repair_requests import (
            OpenHandsOptions,
            RepairOptions,
            assemble_native,
            assemble_openhands,
        )

        options_type, assemble = (
            (OpenHandsOptions, assemble_openhands)
            if args.command == "repair-openhands"
            else (RepairOptions, assemble_native)
        )
        spec = assemble(
            root=args.root,
            upstream_execution_id=args.upstream_execution_id,
            candidate_ids=tuple(args.candidate_id),
            writable_paths=tuple(args.writable),
            readable_paths=tuple(args.readable),
            max_changed_files=args.max_changed_files,
            options=options_type.model_validate_json(args.options.read_bytes()),
            dependency_lock=args.dependency_lock,
            actor=args.actor,
            confirmation_reason=args.reason,
        )
        sys.stderr.write(
            json.dumps(
                {
                    "execution_id": str(spec.execution_id),
                    "status": "prepared",
                    "input_digest": digest(spec),
                }
            )
            + "\n"
        )
        resources = load_resources(args.resources, spec, root=args.root)
        return execute(spec, root=args.root, settings=resources).model_dump(mode="json")
    if args.command == "capabilities":
        return capabilities()
    if args.command == "schema":
        return SCHEMAS[args.kind]()
    if args.command == "cancel":
        # WIRE-SEND:research.control — peer: runtime.control.LocalControl.request_cancel.
        # AGENT: retain command ID/revision and request-only semantics at both ends;
        # requesting cancellation never asserts the external process has stopped.
        if args.execution_id:
            from semflow_research.public.runs import cancellation_command

            command = cancellation_command(args.execution_id, root=args.root)
        else:
            command = ControlCommand.model_validate_json(args.command_file.read_bytes())
        cancel(command, root=args.root)
        return {
            "execution_id": str(command.execution_id),
            "cancellation_requested": True,
        }
    if args.command == "capture-source":
        return capture_source(
            args.directory,
            root=args.root,
            owner_execution_id=args.owner_execution_id,
            languages=tuple(args.language),
        ).model_dump(mode="json")
    if args.command in {"validate", "run"}:
        # WIRE-SEND:research.run — peer: semflow_contracts.runs.validate_spec.
        # This passes frozen research identities/fields, never platform IDs or inferred defaults.
        # AGENT: changes require checking wire.py and the receiving validator together.
        spec = validate_spec(json.loads(args.spec.read_text(encoding="utf-8")))
        if args.command == "run":
            resources = load_resources(args.resources, spec, root=args.root)
            return execute(spec, root=args.root, settings=resources).model_dump(
                mode="json"
            )
        return {
            "valid": True,
            "scope": "contract_structure_only",
            "module": spec.module,
            "operation": spec.operation,
            "input_digest": digest(spec),
            "meaning": "Source, evidence, resources and execution have not been evaluated",
        }
    result = inspect(args.execution_id, root=args.root)
    if result is None:
        return {
            "execution_id": str(args.execution_id),
            "result": None,
            "meaning": "No result manifest has been published",
        }
    return result.model_dump(mode="json")


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        payload = dispatch(args)
    except ValidationError as exc:
        payload = {
            "code": "invalid_contract",
            "errors": exc.errors(include_input=False, include_context=False),
        }
    except ResearchError as exc:
        payload = {"code": exc.code, "message": str(exc)}
    except (OSError, json.JSONDecodeError):
        payload = {
            "code": "invalid_contract",
            "message": "Cannot read the supplied research JSON input",
        }
    else:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return {
            "failed": 1,
            "awaiting_input": 3,
            "cancelled": 130,
            "interrupted": 4,
        }.get(payload.get("execution_status"), 0)
    sys.stderr.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 2
