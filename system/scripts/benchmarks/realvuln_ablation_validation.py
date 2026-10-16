"""Verify frozen dataset and all independent review pool identities."""

from pathlib import Path

from scripts.benchmarks.realvuln_ablation_io import read
from scripts.benchmarks.realvuln_prepare import save


def validate(output):
    config = read(output / "config.json")
    expected = config["review_policy"]
    identities = []
    for group in "DEF":
        paths = sorted((output / "arms" / group / "system").glob("*/review.json"))
        if len(paths) != 26:
            raise RuntimeError(f"{group} has not covered all 26 projects")
        for path in paths:
            record = read(path)
            stage = record["stage"]
            if stage["status"] not in {"completed", "failed", "cancelled"}:
                raise RuntimeError(f"Review has no terminal receipt: {path}")
            final = read(path.parent / "result.json")
            if final.get("provider_interrupted"):
                raise RuntimeError(f"Provider interruption has not been recovered: {path}")
            expected_inputs = {
                "finding_ids": [],
                "paths": [],
                "discover": True,
                "max_steps": 8,
                "max_context_chars": 40000,
                "include_scout": group != "D",
                "scout_candidate_ids": [],
                "batch_size": 4,
                "max_batches": 0,
            }
            if stage["inputs"] != expected_inputs:
                raise RuntimeError(f"Review request differs: {path}")
            pool = stage["result"].get("pool", {})
            if pool.get("inputs") != expected_inputs:
                raise RuntimeError(f"Persisted pool request differs: {path}")
            registration_path = path.parent / "input.json"
            if registration_path.exists():
                inputs = read(registration_path)
                if (
                    stage["audit_id"] != inputs["audit_id"]
                    or pool.get("snapshot") != inputs["snapshot"]
                ):
                    raise RuntimeError(f"Review audit/source identity differs: {path}")
            policy = {
                k: v
                for k, v in stage["model_config_snapshot"].items()
                if k != "prompt_snapshot"
            }
            policy.setdefault("semantic_policy", expected["semantic_policy"])
            if policy != expected:
                raise RuntimeError(f"Review execution policy differs: {path}")
            if stage["prompt_version"] != "12":
                raise RuntimeError("Review prompt version differs")
            origins = {
                r["origin"] for r in stage["result"].get("pool", {}).get("entries", [])
            }
            if (
                group == "D"
                and origins - {"static"}
                or group == "E"
                and origins - {"scout"}
            ):
                raise RuntimeError(f"Independent candidate pool leaked: {path}")
            prompt_hashes = {
                c.get("prompt_hash")
                for c in stage["model_calls"]
                if c.get("prompt_hash")
            }
            actual_models = {
                c["response_model"]
                for c in stage["model_calls"]
                if c.get("response_model")
            }
            if actual_models - {"deepseek-v4-1-flash-260910"}:
                raise RuntimeError(f"Actual response model drifted: {path}")
            if prompt_hashes - {
                "50d48adf1ff39d1bc153adb68babb207a1488d458714acf26f8edb0ec9c5ded8"
            }:
                raise RuntimeError("Actual prompt content drifted")
            identities.append(
                {
                    "group": group,
                    "project_id": path.parent.name,
                    "stage_id": stage["id"],
                    "status": stage["status"],
                    "coverage_status": stage["result"].get("coverage_status"),
                    "pool_origins": sorted(origins),
                    "actual_response_models": sorted(
                        {
                            c["response_model"]
                            for c in stage["model_calls"]
                            if c.get("response_model")
                        }
                    ),
                    "unknown_response_model_calls": sum(
                        not c.get("response_model") for c in stage["model_calls"]
                    ),
                    "prompt_hashes": sorted(prompt_hashes),
                    "policy_verified": True,
                    "receipt": str(path),
                }
            )
    save(output / "formal-review-identity.json", identities)
    return identities


def validate_sources(base, output):
    from app.adapters.snapshot import snapshot_digest
    from scripts.benchmarks.realvuln_ablation_io import sha
    from scripts.benchmarks.realvuln_compare import validate_inputs
    from scripts.benchmarks.realvuln_run import verify_implementation

    verify_implementation(output)
    reference = base / "20261013-progress-v2"
    origins = read(base / "20261013-progress-v3-retest/incremental-report-data.json")[
        "provenance"
    ]
    for origin in {Path(p) for p in origins.values()}:
        validate_inputs(reference, origin)
    for project, origin in origins.items():
        acquisition = read(Path(origin) / "acquisition" / f"{project}.json")
        if (
            snapshot_digest(Path(origin) / "sources" / project)
            != acquisition["snapshot"]
        ):
            raise RuntimeError(f"Final source verification failed: {project}")
    for name, expected in read(reference / "dataset.json")["gold_sha256"].items():
        if (
            "__pycache__" not in Path(name).parts
            and not name.endswith(".pyc")
            and sha(reference / "evaluator-only" / name) != expected
        ):
            raise RuntimeError("Final evaluator/annotation verification failed")
