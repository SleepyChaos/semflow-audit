"""Freeze a bounded A–F discovery/review comparison via research public APIs."""

import argparse
import json
from pathlib import Path
from random import Random
from types import SimpleNamespace
from uuid import uuid4

from semflow_contracts.runs import validate_spec
from semflow_research.public.configuration import load_resources
from semflow_research.public.discovery_requests import (
    DiscoveryOptions,
    assemble_discovery,
)
from semflow_research.public.discovery_results import read_result
from semflow_research.public.implementation import code_digest
from semflow_research.public.runs import capture_source, execute, inspect

# Operation, specification guidance, review. F isolates guidance with review held fixed.
ARMS = {
    "A": ("scout", False, False),
    "B": ("scout", True, False),
    "C": ("discover", False, False),
    "D": ("discover", True, False),
    "E": ("discover", True, True),
    "F": ("discover", False, True),
}


def freeze_matrix(args):
    options = DiscoveryOptions.model_validate_json(args.options.read_bytes())
    policy = options.policy
    if (
        options.security_specifications is None
        or options.model is None
        or options.scout_method_version != "8"
        or options.review_method_version != "12"
        or not all((policy.max_calls, policy.max_tokens, policy.max_seconds))
        or options.max_branch_calls is None
        or options.max_branch_calls >= policy.max_calls
    ):
        raise ValueError(
            "Provide frozen guidance, supported methods, a model and bounded scout/total budgets."
        )
    # Planning requires installed packs and a resource profile, not credentials.
    plan_profile = SimpleNamespace(policy=policy, model=None, inputs=None)
    resources = load_resources(args.resources, plan_profile, root=args.root)
    snapshot = capture_source(
        args.source,
        root=args.root,
        owner_execution_id=uuid4(),
        languages=(options.language,),
    )
    specs = {}
    for arm, (operation, guidance, review) in ARMS.items():
        configured = options.model_copy(
            update={
                "operation": operation,
                "security_specifications": options.security_specifications
                if guidance
                else None,
                "run_review": review,
                "evidence_navigation": True,
                "strict_refutations": review,
                "required_branches": ("scan", "scout"),
                "supplement_insufficient": review,
            }
        )
        spec = assemble_discovery(
            root=args.root,
            options=configured,
            resources=resources,
            dependency_lock=args.dependency_lock,
            source_snapshot=snapshot,
        )
        specs[arm] = spec.model_dump(mode="json")
    order = list(ARMS)
    Random(args.order_seed).shuffle(order)
    manifest = {
        "schema": "semflow.vulinstruct-matrix/1",
        "tree_sha256": snapshot.tree_sha256,
        "snapshot_id": str(snapshot.snapshot_id),
        "order": order,
        "max_total_calls": len(ARMS) * policy.max_calls,
        "specs": specs,
    }
    with args.plan.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return manifest


def run_matrix(args, manifest):
    for arm in manifest["order"]:
        spec = validate_spec(manifest["specs"][arm])
        if (
            spec.implementation.code_digest != code_digest()
            or spec.source.tree_sha256 != manifest["tree_sha256"]
            or str(spec.source.snapshot_id) != manifest["snapshot_id"]
        ):
            raise ValueError(
                "Frozen matrix version or source differs. Use the original executable."
            )
        previous = inspect(spec.execution_id, root=args.root, missing_ok=True)
        if previous is None:
            resources = load_resources(args.resources, spec, root=args.root)
            previous = execute(spec, root=args.root, settings=resources)
        row = {
            "arm": arm,
            "execution_id": str(spec.execution_id),
            "status": previous.execution_status,
            "failure": previous.failure.code if previous.failure else None,
            "usage": previous.usage.model_dump(mode="json"),
        }
        if previous.result:
            view = read_result(spec.execution_id, root=args.root)
            row["candidate_count"] = len(view.candidates)
            row["candidate_origins"] = sorted(
                {candidate.origin for candidate in view.candidates}
            )
            row["review_states"] = [
                "refuted"
                if assessment.conclusion == "excluded"
                else assessment.conclusion
                for assessment in view.assessments
            ]
            row["branches"] = [
                {
                    "role": branch.branch,
                    "id": str(branch.execution_id),
                    "status": branch.status,
                }
                for branch in previous.result.branches
            ]
        print(json.dumps(row, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--resources", type=Path, required=True)
    parser.add_argument("--options", type=Path)
    parser.add_argument("--dependency-lock", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--order-seed", type=int, default=20261119)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.plan.is_file():
        if any((args.source, args.options, args.dependency_lock)):
            parser.error(
                "Resume an existing plan without new source, options or dependency lock."
            )
        manifest = json.loads(args.plan.read_bytes())
    else:
        if not all((args.source, args.options, args.dependency_lock)):
            parser.error("Creating a plan needs source, options and a dependency lock.")
        manifest = freeze_matrix(args)
    if args.execute:
        run_matrix(args, manifest)
    else:
        print(json.dumps({k: v for k, v in manifest.items() if k != "specs"}, indent=2))


if __name__ == "__main__":
    main()
