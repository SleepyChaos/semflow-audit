"""Execution coverage derived from submitted source ranges and accepted receipts."""

import json
from collections import Counter, defaultdict

from semflow_contracts.errors import Failure
from semflow_research.runtime.execution import KernelOutcome, failure_category


def scout_coverage(project, units, selected, directory, stop_reason):
    done = {row["unit_id"] for row in units if row["status"] == "inspected"}
    errors = Counter(row["code"] for row in units if row.get("code"))
    errors.update(row["code"] for row in project["skipped"] if row.get("code"))
    sent, inspected = defaultdict(list), defaultdict(list)
    submitted = set()
    for path in directory.glob("units/*/call-*/source-input.json"):
        body = json.loads(path.read_bytes())
        unit_id = body["unit_id"]
        submitted.add(unit_id)
        for row in body["ranges"]:
            location = (row["start_line"], row["end_line"])
            sent[row["file"]].append(location)
    for unit_id in sorted(done):
        path = directory / "units" / unit_id / "evidence-coverage.json"
        if not path.is_file():
            continue
        for row in json.loads(path.read_bytes()):
            inspected[row["file"]].append((row["start_line"], row["end_line"]))
    functions = {}
    for file in project["files"]:
        ranges = inspected[file["file"]]
        supplied = sent[file["file"]]
        functions[file["file"]] = [
            {
                "qualified_name": row["qualified_name"],
                "start_line": row["start_line"],
                "end_line": row["end_line"],
                "supplied": any(
                    start <= row["end_line"] and end >= row["start_line"]
                    for start, end in supplied
                ),
                "inspected": any(
                    start <= row["end_line"] and end >= row["start_line"]
                    for start, end in ranges
                ),
                "whole_function": any(
                    start <= row["start_line"] and end >= row["end_line"]
                    for start, end in ranges
                ),
            }
            for row in file.get("functions", ())
        ]
    all_functions = [row for values in functions.values() for row in values]
    reasons = list(
        dict.fromkeys(
            filter(
                None,
                [
                    stop_reason,
                    *sorted(errors),
                    "window_limit" if len(selected) < len(project["units"]) else None,
                    "zero_inspected_windows" if not done else None,
                ],
            )
        )
    )
    return {
        "selected_window_ids": [row["id"] for row in selected],
        "submitted_window_ids": sorted(submitted),
        "source_input_ranges": dict(sent),
        "source_inspected_ranges": dict(inspected),
        "function_coverage": functions,
        "indexed_python_files": sum(
            r.get("parse_status") == "indexed" for r in project["files"]
        ),
        "failed_python_indexes": sum(
            r.get("parse_status") == "failed" for r in project["files"]
        ),
        "files_with_model_input": sum(bool(ranges) for ranges in sent.values()),
        "indexed_functions": len(all_functions),
        "functions_with_model_input": sum(row["supplied"] for row in all_functions),
        "functions_inspected": sum(row["inspected"] for row in all_functions),
        "whole_functions_inspected": sum(
            row["whole_function"] for row in all_functions
        ),
        "error_counts": dict(errors),
        "reason_codes": reasons,
    }


def empty_scout_outcome(context, output):
    record = context.execution_records.get(context.execution_id)
    coverage = record.result["coverage"]
    reasons = set(coverage.get("reason_codes", ()))
    if reasons & {"budget_exhausted", "unit_budget", "context_budget"}:
        code = "budget_exhausted"
    elif reasons & {"schema_invalid", "length", "incomplete", "model_output_invalid"}:
        code = "model_output_invalid"
    elif reasons & {"provider_error", "timeout", "rate_limited"}:
        code = "model_unavailable"
    else:
        code = "parse_failed" if "source_unreadable" in reasons else "tool_failed"
    return KernelOutcome(
        result=output,
        failure=Failure(
            code=code,
            category=failure_category(code),
            message="Scout produced no valid source-window assessment. Coverage and attempt receipts are preserved.",
            retryable=code
            in {"budget_exhausted", "model_unavailable", "model_output_invalid"},
            phase=record.phase,
            detail=output.analysis_trace,
        ),
    )
