"""Evaluator-only signed model receipts and reversible source transformations."""

import copy
import hashlib
import json
from pathlib import Path

from app.contracts.discovery_semantics import (
    FinalUnifiedReviewResponseV8,
    UnifiedReviewResponseV8,
)
from app.domain.audit import AuditError
from app.services.context_materials import digest


def read(path):
    return json.loads(path.read_text())


def assessment_key(row):
    return {k: v for k, v in row.items() if k != "evidence_ids"}


def accepted_records(root, output):
    directory = root / "artifacts/runs" / output["stage_id"]
    records = {}
    for batch in output["stage"]["result"].get("batches", []):
        responses = []
        for path in sorted(
            (directory / "batches" / batch["batch_id"]).glob("call-*/receipt.json")
        ):
            receipt = read(path)
            request = read(path.with_name("input.json"))
            payload = request["payload"]
            schema = (
                FinalUnifiedReviewResponseV8
                if payload.get("finalize_required")
                else UnifiedReviewResponseV8
            )
            assert (
                request["input_hash"]
                == receipt["input_hash"]
                == digest({"payload": payload, "schema": schema.model_json_schema()})
            )
            assert receipt["output_hash"] == digest(receipt["output"])
            if receipt["output"]["action"] == "final":
                responses.append((payload, receipt["output"], path))
        for accepted in batch.get("assessments", []):
            matches = [
                (payload, response, path)
                for payload, response, path in responses
                if any(
                    assessment_key(r) == assessment_key(accepted)
                    for r in response["candidate_assessments"]
                )
            ]
            assert matches, (batch["batch_id"], accepted["candidate_id"])
            payload, response, path = matches[-1]
            records[accepted["candidate_id"]] = {
                "context": payload,
                "assessment": accepted,
                "receipt": str(path.relative_to(root)),
                "raw_duplicate_count": sum(
                    r["candidate_id"] == accepted["candidate_id"]
                    for r in response["candidate_assessments"]
                ),
            }
    return records


class ReadOnlySnapshot:
    def __init__(self, root, language, scopes):
        from types import SimpleNamespace

        self.root = Path(root).resolve()
        self.audit = SimpleNamespace(language=language)
        self.scopes = [(self.root / p).resolve() for p in scopes]

    def allowed(self, file):
        if not file or Path(file).is_absolute() or "\\" in file or ":" in file:
            raise AuditError("Invalid replay source path", code="identity_error")
        path = (self.root / file).resolve()
        if (
            not path.is_relative_to(self.root)
            or not path.is_file()
            or not any(path.is_relative_to(p) for p in self.scopes)
        ):
            raise AuditError(
                "Replay source outside original scope", code="identity_error"
            )
        return path

    def verify_materials(self, context):
        for material in context["evidence"]:
            assert (
                hashlib.sha256(material["content"].encode()).hexdigest()
                == material["digest"]
            )
            if material["kind"] != "code":
                continue
            ref = material["reference"]
            lines = self.allowed(ref["file"]).read_text().splitlines()
            body = "\n".join(lines[ref["start_line"] - 1 : ref["end_line"]])
            assert body == material["content"], (ref, "actual source differs")


def clone_sources(source, destination, rename=False, shift=0):
    mapping = {}
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        assert not path.is_symlink()
        old = path.relative_to(source).as_posix()
        new = old
        if rename:
            if path.name.startswith("Case") and path.suffix == ".py":
                new = f"modules/unit_{hashlib.sha256(old.encode()).hexdigest()[:16]}.py"
            elif old == "app.py":
                new = "bootstrap_entry.py"
            new = "renamed_workspace/" + new
        target = destination / new
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(
            (b"\n" * shift if path.suffix == ".py" else b"") + path.read_bytes()
        )
        mapping[old] = new
    return mapping


def transform(value, mapping, shift):
    """Map reference paths/locations, leaving hypotheses and source quotes untouched."""
    if isinstance(value, list):
        return [transform(v, mapping, shift) for v in value]
    if not isinstance(value, dict):
        return copy.deepcopy(value)
    result = {k: transform(v, mapping, shift) for k, v in value.items()}
    if value.get("file") in mapping:
        result["file"] = mapping[value["file"]]
        if value["file"].endswith(".py"):
            for key in ("line", "end_line", "start_line", "reported_line"):
                if isinstance(value.get(key), int):
                    result[key] = value[key] + shift
    return result


def transform_context(context, mapping, shift):
    result = transform(context, mapping, shift)
    # Only explicit navigation arrays/scopes change; natural-language reasoning stays frozen.
    result["paths"] = [
        new
        for old, new in mapping.items()
        if any(
            old == scope or old.startswith(scope.rstrip("/") + "/")
            for scope in context["paths"]
        )
    ]
    return result
