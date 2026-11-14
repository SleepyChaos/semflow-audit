"""Algorithm extracted from app.services.repair_suite_checks.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Use an explicitly selected frozen suite inside finite candidate feedback."""
import json

from semflow_research.adapters.repair.verification_runner import (
    resolve_image,
    run_suite,
)
from semflow_research.adapters.snapshot import snapshot_digest
from semflow_research.domain.errors import AuditError
from semflow_research.evidence.context_materials import digest, save_json
from semflow_research.repair.verification_results import compare_runs
from semflow_research.repair.verification_suites import read_suite


def _execute(
    directory,
    identity,
    workspace,
    tests,
    suite,
    image,
    repository,
    execution_id,
    *,
    _kernel,
):
    receipt = directory / "execution.json"
    if receipt.exists():
        saved = json.loads(receipt.read_text())
        if saved["identity"] != identity or saved["result_hash"] != digest(
            saved["result"]
        ):
            raise AuditError("修复验收执行收据身份或内容变化", code="integrity_error")
        return saved["result"]
    if directory.exists():
        raise AuditError("修复验收上次执行未完整提交，保留产物并创建新阶段")
    repository.active(execution_id)
    result = run_suite(workspace, tests, suite, image, directory, _kernel=_kernel)
    save_json(
        receipt, {"identity": identity, "result": result, "result_hash": digest(result)}
    )
    return result


def _baseline_valid(suite, runs):
    if (
        len(runs) != 2
        or {case.category for case in suite.cases} != {"security", "functional"}
        or any(row.get("status") != "completed" for row in runs)
    ):
        return False
    return all(
        [
            run.get("cases", {}).get(case.name, {}).get("status", "missing")
            for run in runs
        ]
        == (["assertion_failed"] * 2 if case.category == "security" else ["passed"] * 2)
        for case in suite.cases
    )


def check_selected_suite(repair, state, *, _kernel):
    service = repair.service
    if not service.inputs.verification_suite_id:
        return None
    context = repair.context(state)
    stage, suite, tests = read_suite(
        service.inputs.verification_suite_id,
        service.execution.snapshot_id,
        _kernel=_kernel,
    )
    image = context["verification_image_id"]
    if resolve_image(image) != image:
        raise AuditError("已冻结的验收镜像不可用", code="environment_error")
    identity = {
        "suite_id": str(stage.id),
        "suite_hash": stage.result["suite_hash"],
        "test_files_hash": stage.result["test_files_hash"],
        "source_snapshot": service.evidence.source_context.snapshot_hash,
        "image_id": image,
    }
    if snapshot_digest(service.evidence.root) != identity["source_snapshot"]:
        raise AuditError("原始源码变化，不能执行候选验收", code="integrity_error")
    before = []
    for index in range(2):
        before.append(
            _execute(
                (
                    repair.directory / "selected-suite-baseline"
                    if _kernel.spec.inputs.method_policy.baseline_reuse
                    else repair.directory
                    / f"attempt-{state['attempt']}"
                    / "selected-suite-baseline"
                )
                / f"run-{index + 1}",
                {**identity, "side": "before", "repeat": index + 1},
                service.evidence.root,
                tests,
                suite,
                image,
                service.repository,
                service.execution_id,
                _kernel=_kernel,
            )
        )
    latest, _, _ = read_suite(
        service.inputs.verification_suite_id,
        service.execution.snapshot_id,
        _kernel=_kernel,
    )
    if (latest.result["suite_hash"], latest.result["test_files_hash"]) != (
        identity["suite_hash"],
        identity["test_files_hash"],
    ) or snapshot_digest(service.evidence.root) != identity["source_snapshot"]:
        raise AuditError("原始验收执行期间测试或源码变化", code="integrity_error")
    if not _baseline_valid(suite, before):
        return {
            "status": "blocked",
            "category": "inconclusive",
            "output": "所选测试在原代码上未稳定复现安全断言失败或正常功能基线；不据此修改业务代码",
            "identity": identity,
            "before": before,
            "evidence_refs": [
                ref for run in before for ref in run.get("evidence_refs", ())
            ],
        }
    workspace = repair.directory / f"attempt-{state['attempt']}" / "workspace"
    candidate_hash = snapshot_digest(workspace)
    pairs = []
    for index in range(2):
        after = _execute(
            repair.directory
            / f"attempt-{state['attempt']}"
            / "selected-suite"
            / f"run-{index + 1}",
            {
                **identity,
                "patched_snapshot": candidate_hash,
                "side": "after",
                "repeat": index + 1,
            },
            workspace,
            tests,
            suite,
            image,
            service.repository,
            service.execution_id,
            _kernel=_kernel,
        )
        pairs.append({"before": before[index], "after": after})
    latest, _, _ = read_suite(
        service.inputs.verification_suite_id,
        service.execution.snapshot_id,
        _kernel=_kernel,
    )
    if (
        (latest.result["suite_hash"], latest.result["test_files_hash"])
        != (identity["suite_hash"], identity["test_files_hash"])
        or snapshot_digest(service.evidence.root) != identity["source_snapshot"]
        or snapshot_digest(workspace) != candidate_hash
    ):
        raise AuditError("候选验收期间测试或源码发生变化", code="integrity_error")
    result = compare_runs(suite, pairs)
    from semflow_research.repair.repair_runtime_diagnosis import (
        candidate_runtime_errors,
    )

    runtime_errors = candidate_runtime_errors(suite, pairs, workspace)
    runtime_names = {row["test"] for row in runtime_errors}
    implementation_error = (
        result["status"] == "inconclusive"
        and bool(result["uncertain"])
        and set(result["uncertain"]).issubset(runtime_names)
        and all(pair["after"].get("status") == "completed" for pair in pairs)
    )
    if implementation_error:
        result["status"] = "failed"
        result["summary"] = (
            "已校准基线后，完整执行发现候选引入明确名称解析错误；需修正候选，不能算安全通过。"
        )
    return {
        "status": "blocked" if result["status"] == "inconclusive" else result["status"],
        "category": "inconclusive"
        if result["status"] == "inconclusive"
        else "implementation",
        "output": result["summary"],
        "cases": result["cases"],
        "identity": {**identity, "patched_snapshot": candidate_hash},
        "candidate_identity": {
            "snapshot_id": str(service.execution.snapshot_id),
            "execution_id": str(service.execution_id),
            "attempt": state["attempt"],
            "patched_snapshot": candidate_hash,
            "proposal_hash": state.get("proposal_hash"),
        },
        "runtime_errors": runtime_errors,
        "meaning": result["meaning"],
        "evidence_refs": [
            ref
            for pair in pairs
            for run in pair.values()
            for ref in run.get("evidence_refs", ())
        ],
        "baseline_reused_across_candidates": _kernel.spec.inputs.method_policy.baseline_reuse,
    }


def suite_diagnosis(checks):
    result = checks.get("selected_suite")
    if result is None or result["status"] == "passed":
        return None
    return {
        "category": result["category"],
        "summary": result["output"],
        "candidate_identity": result.get("candidate_identity"),
        "failed_cases": [
            {
                key: case.get(key)
                for key in (
                    "name",
                    "category",
                    "candidate_ids",
                    "input_description",
                    "expected_behavior",
                    "before",
                    "after",
                    "stable",
                    "reason",
                )
            }
            for case in result.get("cases", [])
            if case["after"] != "passed"
        ],
        "runtime_errors": result.get("runtime_errors", []),
        "violated_constraints": [
            case["name"] + ": " + case["reason"]
            for case in result.get("cases", [])
            if case["after"] != "passed"
        ],
        "next_action": "Correct the candidate using the unchanged selected acceptance expectations"
        if result["status"] == "failed"
        else "Resolve baseline or execution uncertainty; do not guess a code change",
    }
