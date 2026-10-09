"""Full proof-gate replay and metamorphic checks on frozen OWASP model outputs."""

import copy
import hashlib
import json
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

from app.adapters.snapshot import snapshot_digest
from app.contracts.discovery_semantics import SemanticAssessment
from app.domain.audit import AuditError
from app.services.read_tools import grounded
from app.services.review_classification import decision
from app.services.review_verdict_gate import validate_assessment
from discovery_replay_materials import (
    ReadOnlySnapshot,
    accepted_records,
    clone_sources,
    read,
    transform,
    transform_context,
)

from scripts.benchmarks.formal_scoring import score_cases

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "artifacts/research/owasp-discovery/20261007-pilot-v1"
OUT = ROOT / "artifacts/research/discovery-generalization/20261007-host-replay-v1"
SOURCE = (
    ROOT
    / "benchmark-data/model-inputs/20261005-loader-correction/owasp-python-loader-fixed"
)


def evaluate(record, source, legacy=False):
    context = copy.deepcopy(record["context"])
    targets = {t["candidate_id"]: t for t in context["targets"]}
    if legacy:
        # Functional compatibility with pre-fix CWE-based gate dispatch; all proof rules unchanged.
        for target in targets.values():
            target["weakness"] = "unknown"
            if isinstance(target.get("hypothesis"), dict):
                target["hypothesis"]["weakness"] = "unknown"
            if "static_alert" in target:
                target["static_alert"]["tags"] = []
    adapter = ReadOnlySnapshot(source, context["language"], context["paths"])
    adapter.verify_materials(context)
    service = SimpleNamespace(
        stage=SimpleNamespace(prompt_version="8"), evidence=adapter
    )
    seen = {m["id"]: m for m in context["evidence"]}

    def evidence(ids, location=None):
        if not set(map(str, ids)) <= seen.keys():
            raise AuditError("Unprovided citation")
        rows = [seen[str(i)] for i in set(ids)]
        if location and not grounded(rows, location):
            raise AuditError("Ungrounded primary position")
        return rows

    assessment = SemanticAssessment.model_validate(record["assessment"])
    try:
        if record["raw_duplicate_count"] != 1:
            raise AuditError("Duplicate assessment identity")
        validate_assessment(service, assessment, context, targets, evidence)
    except AuditError as exc:
        return {
            "accepted": False,
            "verdict": "unknown",
            "reason": str(exc),
            "code": exc.code,
        }
    return {"accepted": True, "verdict": assessment.assessment}


def main():
    started = time.monotonic()
    frozen_runner = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [
            Path(__file__),
            Path(__file__).with_name("discovery_replay_materials.py"),
        ]
    }
    frozen_host = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT / "backend/app").rglob("*")
        if p.is_file() and p.suffix in {".py", ".txt"}
    }
    baseline = read(RUN / "evaluation.json")
    labels = baseline["scores"]["D0_CodeQL"]["overall"]["cases"]
    source_identity = snapshot_digest(SOURCE)
    assert source_identity == read(RUN / "config.json")["snapshot"]
    entries, candidates, records, hashes = {}, {}, {}, {}
    for path in sorted(RUN.glob("batch-*/review.json")):
        output = read(path)
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        entries.update(
            {e["candidate_id"]: e for e in output["stage"]["result"]["pool"]["entries"]}
        )
        candidates.update({c["id"]: c for c in output["candidates"]})
        records.update(accepted_records(ROOT, output))
    assert len(candidates) == 184 and len(records) == 180
    old, fixed, reasons = {}, {}, []
    for identifier, record in records.items():
        old[identifier] = evaluate(record, SOURCE, legacy=True)
        fixed[identifier] = evaluate(record, SOURCE)
        assert old[identifier]["accepted"], (identifier, old[identifier])
        assert old[identifier]["verdict"] == candidates[identifier]["model_assessment"]
        if not fixed[identifier]["accepted"]:
            reasons.append({"id": identifier, **fixed[identifier]})
    predictions, changes = [], []
    for identifier, candidate in candidates.items():
        result = fixed.get(identifier, {"accepted": False, "verdict": "unknown"})
        entry = entries[identifier]
        h = entry.get("hypothesis", {})
        original = h.get("weakness", "unknown") if isinstance(h, dict) else "unknown"
        reported = (
            records[identifier]["assessment"]["weakness"]
            if identifier in records
            else candidate["weakness"]
        )
        classification = decision(original, reported)
        if result["accepted"] and result["verdict"] == "supported":
            predictions.append(
                {**candidate, "weakness": classification["effective_weakness"]}
            )
            if classification["effective_weakness"] != candidate["weakness"]:
                changes.append({"id": identifier, **classification})
    score = score_cases(labels, predictions)
    # No label or failure-derived sample selection: apply each transform to all accepted records.
    metamorphic = []
    for name, rename, shift in (
        ("directory_and_file_rename", True, 0),
        ("line_offset", False, 17),
        ("combined", True, 17),
    ):
        with tempfile.TemporaryDirectory(prefix="audit-generality-") as temporary:
            clone = Path(temporary)
            mapping = clone_sources(SOURCE, clone, rename=rename, shift=shift)
            clone_identity = snapshot_digest(clone)
            mismatches = []
            for identifier, record in records.items():
                transformed = {
                    **record,
                    "context": transform_context(record["context"], mapping, shift),
                }
                transformed["context"]["snapshot"] = clone_identity
                outcome = evaluate(transformed, clone)
                if outcome != fixed[identifier]:
                    mismatches.append(
                        {
                            "id": identifier,
                            "base": fixed[identifier],
                            "transformed": outcome,
                        }
                    )
            assert snapshot_digest(clone) == clone_identity
            new_labels = [{**l, "file": mapping[l["file"]]} for l in labels]
            new_predictions = transform(predictions, mapping, shift)
            transformed_score = score_cases(new_labels, new_predictions)
            assert transformed_score["counts"] == score["counts"]
            metamorphic.append(
                {
                    "transform": name,
                    "accepted_records": len(records),
                    "mismatches": mismatches,
                    "same_prediction_counts": transformed_score["counts"]
                    == score["counts"],
                }
            )
    assert snapshot_digest(SOURCE) == source_identity
    assert all(
        hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
        for p, h in hashes.items()
    )
    assert all(
        hashlib.sha256(p.read_bytes()).hexdigest() == h
        for p, h in {**frozen_runner, **frozen_host}.items()
    )
    report = {
        "kind": "paired_frozen_response_full_host_gate_replay_not_fresh_model_audit",
        "model_calls": 0,
        "same_inputs_responses_and_original_budget": True,
        "source_snapshot": source_identity,
        "input_hashes": hashes,
        "old_compatibility": "Only CWE gate dispatch and classification preservation differ; other current proof rules identical. All 180 old accepted records reproduced.",
        "candidate_pool": len(candidates),
        "original_accepted_records": len(records),
        "fixed_accepted_records": sum(v["accepted"] for v in fixed.values()),
        "remaining_unreviewed": len(candidates)
        - sum(v["accepted"] for v in fixed.values()),
        "new_binding_rejections": reasons,
        "classification_changes": changes,
        "original_frozen_score": baseline["scores"]["D3_supported_review"]["overall"],
        "fixed_gate_replay_score": score,
        "metamorphic": metamorphic,
        "actual_replay_seconds": time.monotonic() - started,
        "limits": [
            "No new LLM generation, tool selection, scout discovery or latency comparison.",
            "Previously rejected/unknown responses not upgraded through replay; remain unknown.",
            "Rename tests host proof references, not dynamic application startup/loader equivalence.",
            "Historical OWASP exposure; no hidden model generalization, multiple framework or statistical significance claim.",
            "Retained detector CWE is provenance, not independent model taxonomy confirmation.",
        ],
        "implementation_hashes": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in [ROOT / "backend/app"]
            for p in folder.rglob("*")
            if p.is_file() and p.suffix in {".py", ".txt"}
        },
        "runner_hashes": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                Path(__file__),
                Path(__file__).with_name("discovery_replay_materials.py"),
            ]
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {
                "accepted": report["fixed_accepted_records"],
                "unknown": report["remaining_unreviewed"],
                "counts": score["counts"],
                "precision": score["precision"],
                "recall": score["recall"],
                "f1": score["f1"],
                "metamorphic_mismatches": [len(m["mismatches"]) for m in metamorphic],
                "seconds": report["actual_replay_seconds"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
