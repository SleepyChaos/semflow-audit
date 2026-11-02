"""Prepare a bounded 2x2 DVGA saved-context experiment without calling a model."""

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from audit_evidence_feedback import (
    first_seen,
    provider_hash,
    requests_for,
    verify_supplement,
)


def source_windows(requests, before):
    result = {}
    for request in requests.values():
        if min(request["indices"]) >= before:
            continue
        for window in request["payload"].get("source_windows", []):
            result[window["evidence_id"]] = window
    return result


def base_context(original, identifiers):
    context = deepcopy(original)
    context["targets"] = [
        t for t in context["targets"] if t["candidate_id"] in identifiers
    ]
    if {t["candidate_id"] for t in context["targets"]} != identifiers:
        raise ValueError("Replay targets differ from original request")
    context["citation_contract"]["target_source_ids"] = {
        k: v
        for k, v in context["citation_contract"]["target_source_ids"].items()
        if k in identifiers
    }
    # All arms omit the same navigation inventory, preserving every original body.
    context["source_inventory"] = {
        "omitted_for_context": True,
        "meaning": "Saved-context replay; original source bodies retained; no live source tools",
    }
    context["remaining_model_calls_in_batch"] = 1
    context["finalize_required"] = True
    context["allow_supplementary_findings"] = False
    context["server_feedback"] = (
        "Reassess only the supplied targets from actual source evidence. Return final; "
        "unresolved local or policy facts remain insufficient. No live source tool is available."
    )
    return context


def add_pages(context, pages, windows):
    result = deepcopy(context)
    existing = {e["id"] for e in result["evidence"]}
    result["evidence"].extend(e for e in pages if e["id"] not in existing)
    window_ids = {w["evidence_id"] for w in result["source_windows"]}
    result["source_windows"].extend(
        windows[e["id"]] for e in pages if e["id"] not in window_ids
    )
    complete = result["local_control_context"]["provided_complete_modules"]
    for file in sorted({e["reference"]["file"] for e in pages}):
        actual = [w for w in result["source_windows"] if w["file"] == file]
        totals = {w["total_lines"] for w in actual}
        if len(totals) != 1:
            raise ValueError(f"Conflicting saved file lengths: {file}")
        total = totals.pop()
        if (
            all(
                any(w["start_line"] <= n <= w["end_line"] for w in actual)
                for n in range(1, total + 1)
            )
            and file not in complete
        ):
            complete.append(file)
    return result


def prepare(supplement, diagnosis, output, max_chars):
    verified = verify_supplement(supplement)
    plans = json.loads((diagnosis / "dvga-feedback-plan.json").read_text())
    stage_ids, input_files = (
        {p["stage_id"] for p in plans},
        {p["saved_input"] for p in plans},
    )
    if len(stage_ids) != 1 or len(input_files) != 1:
        raise ValueError("Pilot requires one immutable stage/batch input")
    sid, input_file = stage_ids.pop(), input_files.pop()
    stage = json.loads(
        (supplement / "database-records" / sid / "stage.json").read_text()
    )
    requests = requests_for(supplement / "review-stages" / sid, stage)
    original = requests[supplement / input_file]
    before = min(original["indices"])
    observed, windows = first_seen(requests), source_windows(requests, before)
    all_evidence = json.loads(
        (supplement / "database-records" / sid / "evidence.json").read_text()
    )
    wanted = {
        i for p in plans for g in p["named_gaps"] for i in g["earlier_evidence_ids"]
    }
    pages = []
    for evidence in all_evidence:
        if evidence["id"] not in wanted:
            continue
        if (
            evidence["snapshot_hash"] != original["payload"]["snapshot"]
            or evidence["stage_id"] != sid
            or evidence["kind"] != "code"
            or hashlib.sha256(evidence["content"].encode()).hexdigest()
            != evidence["digest"]
            or observed.get(evidence["id"], before) >= before
            or evidence["id"] not in windows
        ):
            raise ValueError(
                "Retrieved page fails immutable snapshot or temporal isolation"
            )
        pages.append(
            {k: evidence[k] for k in ("id", "kind", "reference", "content", "digest")}
        )
    if {e["id"] for e in pages} != wanted:
        raise ValueError(
            "Required existing pages missing; do not substitute new source"
        )
    base = base_context(original["payload"], {p["candidate_id"] for p in plans})
    arms = []
    for name, ledger, supplement_pages in [
        ("R0", False, False),
        ("R1", True, False),
        ("R2", False, True),
        ("R3", True, True),
    ]:
        context = (
            add_pages(base, pages, windows) if supplement_pages else deepcopy(base)
        )
        if ledger:
            context["premise_feedback"] = {
                "tasks": [
                    {"candidate_id": p["candidate_id"], "recheck": p["missing_roles"]}
                    for p in plans
                ],
                "instruction": "Check each missing premise against supplied pages. Availability is not proof; cite actual facts. Missing business policy remains missing.",
            }
        chars = len(json.dumps(context, ensure_ascii=False))
        if chars > max_chars:
            raise ValueError(
                f"{name} exceeds context cap: {chars}>{max_chars}; no evidence truncated"
            )
        arms.append(
            (
                name,
                context,
                {
                    "ledger": ledger,
                    "existing_pages": supplement_pages,
                    "context_chars": chars,
                    "payload_hash": provider_hash(context),
                },
            )
        )
    output.mkdir(parents=True, exist_ok=True)
    for name, context, _ in arms:
        (output / f"{name}.input.json").write_text(
            json.dumps(
                {"input_hash": provider_hash(context), "payload": context},
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
    result = {
        "status": "prepared_not_executed",
        "experiment_type": "saved_context_2x2_development_pilot",
        "verified_supplement_files": verified,
        "stage_id": sid,
        "source_input": input_file,
        "source_provider_hash": provider_hash(original["payload"]),
        "snapshot_hash": original["payload"]["snapshot"],
        "target_count": len(plans),
        "retrieved_existing_page_ids": sorted(wanted),
        "max_context_chars": max_chars,
        "arms": {name: meta for name, _, meta in arms},
        "execution_budget": {
            "max_provider_requests_total": 4,
            "max_requests_per_arm": 1,
            "output_tokens_per_request": 6000,
            "request_timeout_seconds": 90,
            "repetitions": 1,
            "automatic_retries": 0,
        },
        "prerequisites": [
            "Independently adjudicate missing facts without using benchmark labels as policy",
            "Freeze current request/response model identity and response schema before execution",
        ],
        "limits": [
            "No live tool loop, no full source recovery and no discovery rerun",
            "Retrieval uses only pages shown in earlier calls of the same immutable stage",
            "One development batch cannot establish causal generalization or paper-level effect size",
        ],
    }
    (output / "preflight.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--supplement-root", type=Path, required=True)
    parser.add_argument("--diagnosis-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-context-chars", type=int, default=40000)
    args = parser.parse_args()
    prepare(
        args.supplement_root.resolve(),
        args.diagnosis_root.resolve(),
        args.output.resolve(),
        args.max_context_chars,
    )


if __name__ == "__main__":
    main()
