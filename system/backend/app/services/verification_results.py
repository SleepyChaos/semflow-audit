"""Host verdicts from calibrated, repeated test results; never model verdicts."""

import re

LABELS = {
    "passed": "通过",
    "assertion_failed": "断言未通过",
    "error": "执行错误",
    "skipped": "跳过",
    "missing": "未执行",
}


def execution_problem(runs, case_name):
    for run in runs:
        for side in ("before", "after"):
            module = re.search(
                r"ModuleNotFoundError: No module named ['\"]([^'\"\n]+)['\"]",
                run[side].get("output", ""),
            )
            if module:
                return f"测试环境缺少 Python 依赖 {module[1]}，验收用例尚未执行"
    for run in runs:
        for side, label in (("before", "原代码"), ("after", "补丁副本")):
            case = run[side].get("cases", {}).get(case_name, {})
            kind = case.get("exception_type") or "测试错误"
            if case.get("status") == "error":
                return f"{label}执行出现 {kind}，不是安全断言结果，不能判断该项修复"
    return "测试错误、跳过或缺失，不能当作漏洞复现或修复证据"


def compare_runs(suite, runs):
    rows, failures, uncertain = [], [], []
    if len(runs) != 2 or any(
        run[side].get("status") != "completed"
        for run in runs
        for side in ("before", "after")
    ):
        uncertain.append("环境或测试执行未完成，不能判断修复")
    for case in suite.cases:
        before = [
            run["before"].get("cases", {}).get(case.name, {}).get("status", "missing")
            for run in runs
        ]
        after = [
            run["after"].get("cases", {}).get(case.name, {}).get("status", "missing")
            for run in runs
        ]
        stable = len(before) == 2 and len(set(before)) == len(set(after)) == 1
        b, a = (before[0] if before else "missing"), (after[0] if after else "missing")
        reason = ""
        if not stable:
            uncertain.append(case.name)
            reason = "重复运行结果不一致，需排查不稳定测试"
        elif b in {"error", "skipped", "missing"} or a in {
            "error",
            "skipped",
            "missing",
        }:
            uncertain.append(case.name)
            reason = execution_problem(runs, case.name)
        elif case.category == "security":
            if b == "passed":
                uncertain.append(case.name)
                reason = "原代码已经通过这项测试，没有复现目标漏洞"
            elif a != "passed":
                failures.append(case.name)
                reason = "补丁后仍未满足安全断言"
            else:
                reason = "相同安全断言在原代码失败，在补丁副本通过"
        elif b != "passed":
            uncertain.append(case.name)
            reason = "正常功能基线未通过，无法评估是否保持原有功能"
        elif a != "passed":
            failures.append(case.name)
            reason = "原有正常功能在补丁后未通过"
        else:
            reason = "正常功能在修复前后均通过"
        rows.append(
            {
                **case.model_dump(mode="json"),
                "before": b,
                "after": a,
                "before_label": LABELS.get(b, b),
                "after_label": LABELS.get(a, a),
                "stable": stable,
                "reason": reason,
            }
        )
    status = "inconclusive" if uncertain else "failed" if failures else "passed"
    return {
        "status": status,
        "cases": rows,
        "failures": failures,
        "uncertain": uncertain,
        "summary": "在已列出的测试范围内，漏洞复现后被补丁阻断，正常功能保持；仍需审阅测试和补丁。"
        if status == "passed"
        else "对比未达到验收条件，请查看每项测试的原因。",
        "meaning": "Executed assertions cover these cases only; no proof of complete project safety",
        "repetitions": len(runs),
    }
