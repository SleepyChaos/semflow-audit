"""Minimal rule input and explicit human control commands; only research public APIs."""

import json
from pathlib import Path
from uuid import UUID

from semflow_contracts.errors import ResearchError
from semflow_contracts.evidence import ActorRef
from semflow_research.public.actions import decision_command, load_command, save_command
from semflow_research.public.configuration import load_resources
from semflow_research.public.rule_requests import (
    RuleOptions,
    assemble_rule,
    resources_for,
)
from semflow_research.public.runs import execute, resume, specification

COMMANDS = {"rule-generate", "rule-validate", "decide", "resume"}


def add_parsers(commands):
    rule = commands.add_parser(
        "rule-generate",
        help="Assemble source, corpus and method choices for the rule kernel",
    )
    rule.add_argument("--root", type=Path, required=True)
    source = rule.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-directory", type=Path)
    source.add_argument("--upstream-execution-id", type=UUID)
    rule.add_argument("--candidate-id", type=UUID, action="append", default=[])
    rule.add_argument("--confirm", action="store_true")
    rule.add_argument("--actor")
    rule.add_argument("--reason")
    rule.add_argument("--documents", type=Path, required=True)
    rule.add_argument("--options", type=Path, required=True)
    rule.add_argument("--resources", type=Path, required=True)
    rule.add_argument("--dependency-lock", type=Path, required=True)
    decide = commands.add_parser(
        "decide", help="Record approval or rejection of the exact pending rule fixtures"
    )
    decide.add_argument("--root", type=Path, required=True)
    decide.add_argument("--execution-id", type=UUID, required=True)
    decide.add_argument("--actor", required=True)
    decide.add_argument("--reason", required=True)
    decide.add_argument("--reject", action="store_true")
    continuation = commands.add_parser(
        "resume", help="Continue the saved rule checkpoint with a recorded decision"
    )
    continuation.add_argument("--root", type=Path, required=True)
    continuation.add_argument("--decision-file", type=Path, required=True)
    continuation.add_argument("--resources", type=Path, required=True)
    validation = commands.add_parser(
        "rule-validate",
        help="Recheck approved rule fixtures/holdout in a separate execution",
    )
    validation.add_argument("--root", type=Path, required=True)
    validation.add_argument("--decision-file", type=Path, required=True)
    validation.add_argument("--resources", type=Path, required=True)


def dispatch(args):
    if args.command == "rule-validate":
        from semflow_research.public.rule_validation import assemble

        spec = assemble(load_command(args.decision_file), root=args.root)
        resources = load_resources(args.resources, spec, root=args.root)
        return execute(spec, root=args.root, settings=resources).model_dump(mode="json")
    if args.command == "rule-generate":
        options = RuleOptions.model_validate_json(args.options.read_bytes())
        resources = resources_for(args.resources, options, root=args.root)
        if args.candidate_id and not args.confirm:
            raise ResearchError(
                "invalid_contract",
                "Explicit --confirm is required for a selected rule target",
            )
        # WIRE-SEND:research.run — peer: public.rule_requests.assemble_rule.
        # AGENT: caller choices stay explicit; the public codec creates UUIDs,
        # content digests and Prompt refs and validates the original upstream source.
        spec = assemble_rule(
            root=args.root,
            documents=json.loads(args.documents.read_text()),
            options=options,
            resources=resources,
            dependency_lock=args.dependency_lock,
            source_directory=args.source_directory,
            upstream_execution_id=args.upstream_execution_id,
            candidate_ids=tuple(args.candidate_id),
            actor=args.actor,
            confirmation_reason=args.reason,
        )
        return execute(spec, root=args.root, settings=resources).model_dump(mode="json")
    if args.command == "decide":
        command = decision_command(
            args.execution_id,
            root=args.root,
            actor=ActorRef(kind="human", id=args.actor),
            approved=not args.reject,
            reason=args.reason,
        )
        path = save_command(command, root=args.root)
        return {
            "execution_id": str(command.execution_id),
            "command_id": str(command.command_id),
            "approved": command.approval.approved,
            "decision_file": str(path.resolve()),
            "meaning": "Human decision recorded; execution has not resumed",
        }
    # WIRE-SEND:research.control — peer: runtime.control.claim_resume / rules.resume.
    # AGENT: a saved command binds its subject/checkpoint/revision. Resume reads
    # that decision and its original spec; it never creates implicit approval.
    command = load_command(args.decision_file)
    resources = load_resources(
        args.resources,
        specification(command.execution_id, root=args.root),
        root=args.root,
    )
    return resume(command, root=args.root, settings=resources).model_dump(mode="json")
