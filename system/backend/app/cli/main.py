"""semflow: JSON plans in, persistent IDs and machine-readable receipts out."""

import argparse
import json
import logging
import sys
from pathlib import Path
from uuid import UUID


def parser():
    root = argparse.ArgumentParser(
        prog="semflow",
        description="Run SemFlow experiments without HTTP or a task queue",
    )
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("run", "batch", "validate"):
        command = commands.add_parser(name)
        command.add_argument(
            "--config", type=Path, required=True, help="Versioned JSON experiment plan"
        )
        if name == "run":
            command.add_argument(
                "--sample", help="Required when the plan has multiple samples"
            )
    inspect = commands.add_parser("inspect")
    inspect.add_argument(
        "--run-id", type=UUID, required=True, help="Experiment, audit or stage ID"
    )
    inspect.add_argument("--evidence", action="store_true")
    inspect.add_argument("--logs", action="store_true")
    for name in ("resume", "retry", "cancel", "recover"):
        command = commands.add_parser(name)
        command.add_argument("--run-id", type=UUID, required=True, help="Stage ID")
        if name == "resume":
            command.add_argument(
                "--reason",
                required=True,
                help="Explicit human approval of positive/negative rule fixtures",
            )
    decide = commands.add_parser(
        "decide", help="Record an explicit human candidate decision"
    )
    decide.add_argument("--candidate-id", type=UUID, required=True)
    decide.add_argument(
        "--status",
        choices=["confirmed", "excluded", "pending", "insufficient"],
        required=True,
    )
    decide.add_argument("--reason", required=True)
    decide.add_argument("--evidence-id", type=UUID, action="append", default=[])
    return root


def dispatch(args):
    if args.command in {"run", "batch", "validate"}:
        from app.contracts.experiments import ExperimentPlan
        from app.domain.audit import AuditError

        plan = ExperimentPlan.model_validate(
            json.loads(args.config.read_text(encoding="utf-8"))
        )
        for sample in plan.samples:
            if sample.archive is not None:
                sample.archive = (
                    args.config.resolve().parent / sample.archive
                ).resolve()
        if args.command == "validate":
            return {"valid": True, "plan": plan.model_dump(mode="json")}, 0
        from app.cli.experiments import execute_plan

        selected = None
        if args.command == "run":
            selected = args.sample or (
                plan.samples[0].id if len(plan.samples) == 1 else None
            )
            if selected is None:
                raise AuditError("Select one sample with --sample, or use batch")
        result = execute_plan(plan, selected)
        if all(row["status"] == "completed" for row in result["runs"]):
            return result, 0
        waiting = all(
            row["status"] in {"completed", "awaiting_confirmation"}
            for row in result["runs"]
        )
        return result, 3 if waiting else 1
    from app.cli.records import decide_candidate, inspect_record, stage_action

    if args.command == "decide":
        return decide_candidate(
            args.candidate_id, args.status, args.reason, args.evidence_id
        ), 0
    if args.command == "inspect":
        return inspect_record(args.run_id, evidence=args.evidence, logs=args.logs), 0
    result = stage_action(args.command, args.run_id, getattr(args, "reason", None))
    if result["status"] == "awaiting_confirmation":
        return result, 3
    return result, 0 if result["status"] in {"completed", "cancelled"} else 1


def write_json(payload, *, error=False):
    stream = sys.stderr if error else sys.stdout
    stream.write(
        json.dumps(payload, ensure_ascii=False, indent=None if error else 2) + "\n"
    )


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    from pydantic import ValidationError
    from sqlalchemy.exc import SQLAlchemyError

    from app.domain.audit import AuditError
    from app.services.report_materials import redact

    try:
        result, code = dispatch(args)
        write_json(redact(result))
        return code
    except KeyboardInterrupt:
        write_json(
            {
                "error": "interrupted",
                "meaning": "Inspect persisted IDs before recovery or retry",
            },
            error=True,
        )
        return 130
    except SQLAlchemyError:
        write_json(
            {
                "error": "database_error",
                "message": "Database operation failed; check DATABASE_URL, migrations and connectivity",
            },
            error=True,
        )
    except ValidationError as exc:
        write_json(
            {
                "error": "invalid_config",
                "details": exc.errors(
                    include_input=False, include_context=False, include_url=False
                ),
            },
            error=True,
        )
    except (AuditError, OSError, ValueError, KeyError) as exc:
        write_json(
            redact(
                {"error": getattr(exc, "code", "invalid_input"), "message": str(exc)}
            ),
            error=True,
        )
    return 2
