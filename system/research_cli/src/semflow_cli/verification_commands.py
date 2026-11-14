"""Minimal suite and comparison commands; only research public interfaces."""

import json
import sys
from pathlib import Path
from uuid import UUID

from semflow_contracts.common import digest
from semflow_research.public.configuration import load_resources
from semflow_research.public.runs import execute
from semflow_research.public.verification_requests import (
    SuiteOptions,
    VerifyOptions,
    assemble_suite,
    assemble_verify,
)

COMMANDS = {"repair-build-suite", "repair-verify"}


def add_parsers(commands):
    for command in sorted(COMMANDS):
        parser = commands.add_parser(
            command, help="Build frozen assertions or compare a published patch"
        )
        parser.add_argument("--root", type=Path, required=True)
        parser.add_argument("--options", type=Path, required=True)
        parser.add_argument("--resources", type=Path, required=True)
        parser.add_argument("--dependency-lock", type=Path, required=True)
        if command == "repair-build-suite":
            parser.add_argument("--upstream-execution-id", type=UUID, required=True)
            parser.add_argument(
                "--candidate-id", type=UUID, action="append", required=True
            )
            parser.add_argument("--confirm", action="store_true", required=True)
            parser.add_argument("--actor", required=True)
            parser.add_argument("--reason", required=True)
            parser.add_argument("--requirements-file", type=Path, required=True)
        else:
            parser.add_argument("--repair-execution-id", type=UUID, required=True)
            parser.add_argument("--suite-execution-id", type=UUID, required=True)


def dispatch(args):
    common = {"root": args.root, "dependency_lock": args.dependency_lock}
    if args.command == "repair-build-suite":
        spec = assemble_suite(
            **common,
            upstream_execution_id=args.upstream_execution_id,
            candidate_ids=tuple(args.candidate_id),
            options=SuiteOptions.model_validate_json(args.options.read_bytes()),
            actor=args.actor,
            confirmation_reason=args.reason,
            requirements=args.requirements_file.read_text(encoding="utf-8"),
        )
    else:
        spec = assemble_verify(
            **common,
            repair_execution_id=args.repair_execution_id,
            suite_execution_id=args.suite_execution_id,
            options=VerifyOptions.model_validate_json(args.options.read_bytes()),
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
