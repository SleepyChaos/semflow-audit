"""Locate named evidence gaps in saved requests; prepare, but do not execute, feedback."""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from analyze_realvuln_advantages import write_csv
from audit_mechanism_cohort import encoded_rows

SOURCE_PATH = re.compile(
    r"(?<![\w./-])(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+"
    r"\.(?:py|js|ts|jsx|tsx|json|yaml|yml|toml|ini|cfg|html|htm|ejs|vue|svelte|graphql|gql)(?![A-Za-z0-9_./-])"
)


def named_paths(assessment):
    text = json.dumps(
        [
            assessment.get("missing_premises", []),
            [
                p.get("reason", "")
                for p in assessment.get("premises", [])
                if p["status"] == "missing"
            ],
        ],
        ensure_ascii=False,
    )
    return sorted(
        {
            p
            for p in SOURCE_PATH.findall(text)
            if not p.startswith("/") and ".." not in Path(p).parts
        }
    )


def provider_hash(payload):
    # This matches the frozen provider, including its default ensure_ascii=True.
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def requests_for(stage_dir, stage):
    calls = {}
    for call in stage["model_calls"]:
        calls.setdefault(call["input_hash"], []).append(call["call_index"])
    result = {}
    for file in sorted(stage_dir.glob("batches/*/call-*/input.json")):
        payload = json.loads(file.read_text())["payload"]
        indices = calls.get(provider_hash(payload))
        if not indices:
            raise ValueError(f"Saved request has no provider call: {file}")
        receipt = json.loads(file.with_name("receipt.json").read_text())
        result[file] = {"payload": payload, "indices": indices, "receipt": receipt}
    return result


def first_seen(requests):
    result = {}
    for request in requests.values():
        index = min(request["indices"])
        for row in request["payload"]["evidence"]:
            result[row["id"]] = min(result.get(row["id"], index), index)
    return result


def accepted_matches(raw, accepted):
    """Mirror host citation retention for detail, example, then premise evidence."""
    if raw is None:
        return False
    normalized = dict(raw)
    detail = raw.get("detail", {})
    normalized["evidence_ids"] = list(
        dict.fromkeys(
            [
                *raw["evidence_ids"],
                *detail.get("evidence_ids", []),
                *detail.get("exploitation", {}).get("evidence_ids", []),
                *[
                    identifier
                    for p in raw.get("premises", [])
                    for identifier in p["evidence_ids"]
                ],
            ]
        )
    )
    return normalized == accepted


def gap_status(file, context, evidence, observed, call_index):
    supplied = [
        e
        for e in context["evidence"]
        if e["kind"] == "code" and e["reference"].get("file") == file
    ]
    earlier = [
        e
        for e in evidence
        if e["kind"] == "code"
        and e["reference"].get("file") == file
        and observed.get(e["id"], call_index) < call_index
    ]
    windows = [w for w in context.get("source_windows", []) if w["file"] == file]
    complete = any(w.get("complete_file") for w in windows)
    if windows and not complete:
        total = windows[0]["total_lines"]
        complete = all(
            any(w["start_line"] <= n <= w["end_line"] for w in windows)
            for n in range(1, total + 1)
        )
    status = (
        "pages_in_current_request"
        if supplied
        else "pages_seen_in_earlier_stage_call"
        if earlier
        else "pages_retained_in_stage_time_unverified"
        if any(
            e["kind"] == "code" and e["reference"].get("file") == file for e in evidence
        )
        else "no_retained_pages"
    )
    return {
        "file": file,
        "availability": status,
        "complete_in_current_request": complete,
        "current_evidence_ids": [e["id"] for e in supplied],
        "earlier_evidence_ids": [e["id"] for e in earlier],
        "next_action": (
            "reconsider_supplied_pages"
            if complete
            else "inspect_supplied_pages_and_identify_unread_ranges"
            if supplied
            else "retrieve_existing_pages_then_check_coverage"
            if earlier
            else "resolve_snapshot_path_and_read_targeted_pages"
        ),
        "limit": "Page availability is not proof that a vulnerability premise is satisfied",
    }


def verify_supplement(root):
    root = root.resolve()
    manifest = json.loads((root / "MANIFEST.json").read_text())
    for row in manifest:
        path = (root / row["path"]).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Manifest path escapes supplement")
        content = path.read_bytes()
        if (
            len(content) != row["bytes"]
            or hashlib.sha256(content).hexdigest() != row["sha256"]
        ):
            raise ValueError(f"Supplement digest mismatch: {row['path']}")
    return len(manifest)


def stage_rows(root, stage_dir):
    sid = stage_dir.name
    db = root / "database-records" / sid
    stage = json.loads((db / "stage.json").read_text())
    evidence = json.loads((db / "evidence.json").read_text())
    snapshot = stage["result"]["snapshot_hash"]
    for row in evidence:
        if (
            row["snapshot_hash"] != snapshot
            or row["stage_id"] != sid
            or hashlib.sha256(row["content"].encode()).hexdigest() != row["digest"]
        ):
            raise ValueError(f"Cross-snapshot/stage or corrupt evidence: {row['id']}")
    requests = requests_for(stage_dir, stage)
    observed = first_seen(requests)
    recovery = set(stage["result"].get("recovery_attempted_ids", []))
    rows = []
    for batch in stage["result"]["batches"]:
        if not batch.get("assessments"):
            continue
        candidates = [
            (f, r)
            for f, r in requests.items()
            if f.parent.parent.name == batch["batch_id"]
            and r["receipt"]["output"].get("action") == "final"
        ]
        if not candidates:
            raise ValueError(
                f"Accepted batch lacks saved final input: {sid}/{batch['batch_id']}"
            )
        file, request = max(
            candidates, key=lambda item: int(item[0].parent.name.split("-")[1])
        )
        context, index = request["payload"], min(request["indices"])
        output = {
            a["candidate_id"]: a
            for a in request["receipt"]["output"]["candidate_assessments"]
        }
        for assessment in batch["assessments"]:
            identifier = assessment["candidate_id"]
            if not accepted_matches(output.get(identifier), assessment):
                raise ValueError(
                    f"Accepted assessment differs from saved final receipt: {identifier}"
                )
            if assessment["assessment"] != "insufficient":
                continue
            gaps = [
                gap_status(p, context, evidence, observed, index)
                for p in named_paths(assessment)
            ]
            rows.append(
                {
                    "stage_id": sid,
                    "batch_id": batch["batch_id"],
                    "candidate_id": identifier,
                    "snapshot_hash": snapshot,
                    "final_call_index": index,
                    "saved_input": str(file.relative_to(root)),
                    "missing_premises": assessment["missing_premises"],
                    "missing_roles": [
                        p["premise"]
                        for p in assessment["premises"]
                        if p["status"] == "missing"
                    ],
                    "remaining_calls_in_request": context[
                        "remaining_model_calls_in_batch"
                    ],
                    "finalize_required": context["finalize_required"],
                    "recovery_attempted": identifier in recovery,
                    "named_gaps": gaps,
                    "next_step": "candidate_specific_evidence_plan"
                    if gaps
                    else "identify_missing_fact_location",
                    "limit": "Model-declared gap, not an independently adjudicated reasoning error",
                }
            )
    return rows


def run(root, output):
    verified = verify_supplement(root)
    rows = []
    stages = sorted((root / "review-stages").iterdir())
    for stage in stages:
        rows.extend(stage_rows(root, stage))
    dvga = json.loads((root / "cases/dvga-021/case.json").read_text())
    ids = {r["review_candidate_id"] for r in dvga["candidate_mappings"]}
    plans = [r for r in rows if r["candidate_id"] in ids]
    if len(plans) != len(ids):
        raise ValueError("DVGA candidate coverage mismatch")
    summary = {
        "mode": "offline_saved_context_diagnosis_no_new_model_calls",
        "verified_supplement_files": verified,
        "review_stages": len(stages),
        "accepted_insufficient_assessments": len(rows),
        "with_named_local_files": sum(bool(r["named_gaps"]) for r in rows),
        "with_pages_in_current_request": sum(
            any(
                g["availability"] == "pages_in_current_request" for g in r["named_gaps"]
            )
            for r in rows
        ),
        "with_complete_named_file_in_request": sum(
            any(g["complete_in_current_request"] for g in r["named_gaps"]) for r in rows
        ),
        "with_pages_seen_earlier_in_stage": sum(
            any(
                g["availability"] == "pages_seen_in_earlier_stage_call"
                for g in r["named_gaps"]
            )
            for r in rows
        ),
        "finalized_with_calls_available": sum(
            r["remaining_calls_in_request"] > 1 and not r["finalize_required"]
            for r in rows
        ),
        "named_file_signals": dict(
            Counter(g["availability"] for r in rows for g in r["named_gaps"])
        ),
        "dvga_candidate_count": len(plans),
        "limits": [
            "Three selected projects, not the 26-project population; counts are assessment events",
            "A named file can be present while a required fact remains absent; manual adjudication required",
            "Complete original source snapshots missing; this is not a full pipeline rerun",
            "Remaining calls include the current final call and are not additional paid requests",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "saved-context-gaps.csv", encoded_rows(rows))
    for name, data in [
        ("saved-context-summary.json", summary),
        ("dvga-feedback-plan.json", plans),
    ]:
        (output / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--supplement-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.supplement_root.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
