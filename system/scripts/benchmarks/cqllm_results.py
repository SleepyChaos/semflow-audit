"""Reconcile the frozen paired matrix and export auditable result tables."""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from scripts.benchmarks.cqllm_materials import sha
from scripts.benchmarks.mechanical_pipeline import save


def reconcile(root):
    manifest = json.loads((root / "manifest.json").read_text())
    expected = {(arm, t["id"]) for arm in manifest["arms"] for t in manifest["tasks"]}
    rows, ledger = [], []
    for arm, identity in sorted(expected):
        directory = root / "arms" / arm / identity
        generation = directory / "result.json"
        evaluation = directory / "evaluation.json"
        if not generation.exists() or not evaluation.exists():
            raise RuntimeError(f"Incomplete paired result: {arm}/{identity}")
        result = json.loads(generation.read_text())
        checked = json.loads(evaluation.read_text())
        if any(
            r.get("arm") != arm or r.get("task_id") != identity
            for r in (result, checked)
        ):
            raise RuntimeError("Receipt identity differs from frozen matrix")
        compiled = result.get("compile_success", False)
        executed = checked.get("execution_success", False)
        if compiled != (result["status"] == "compiled") or executed != (
            checked["status"] == "executed"
        ):
            raise RuntimeError("Inconsistent compilation/execution receipt")
        if executed and not compiled:
            raise RuntimeError("Execution success without compilation")
        attempt = directory / f"attempt-{result.get('attempt', 1)}"
        compiler_log = attempt / "compile.log"
        diagnostic = (
            compiler_log.read_text(errors="replace")[-6000:]
            if compiler_log.exists()
            else result.get("error", "")
        )
        rows.append(
            {
                "arm": arm,
                "task_id": identity,
                "generation_status": result["status"],
                "first_compile_pass": bool(result.get("first_compile_success")),
                "final_compile_pass": compiled,
                "execution_status": checked["status"],
                "execution_pass": executed,
                "alerts": checked.get("alerts"),
                "semantic_correct": None,
                "error": checked.get("error") or result.get("error"),
                "compiler_diagnostic": diagnostic,
                "generation_sha256": sha(generation),
                "evaluation_sha256": sha(evaluation),
            }
        )
        call_file = directory / "model-calls.json"
        calls = (
            json.loads(call_file.read_text())["records"]
            if call_file.exists()
            else result.get("model_calls", [])
        )
        if not isinstance(calls, list):
            raise TypeError("Model call ledger must be a list")
        for number, call in enumerate(calls, 1):
            ledger.append(
                {
                    "arm": arm,
                    "task_id": identity,
                    "record": number,
                    **{
                        key: call.get(key)
                        for key in (
                            "input_tokens",
                            "output_tokens",
                            "cached_input_tokens",
                            "reasoning_tokens",
                            "seconds",
                            "error_code",
                            "request_model",
                            "response_model",
                        )
                    },
                }
            )
    for kind in ("result.json", "evaluation.json"):
        actual = {
            (p.parent.parent.name, p.parent.name) for p in root.glob(f"arms/*/*/{kind}")
        }
        if actual != expected:
            raise RuntimeError(f"Unexpected {kind} outside frozen matrix")
    return manifest, rows, ledger


def export(root, output):
    manifest, rows, ledger = reconcile(root)
    output.mkdir(parents=True, exist_ok=True)
    for name, values in (("tasks", rows), ("resource-ledger", ledger)):
        with (output / f"{name}.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)
    summary = {"frozen_tasks": len(rows), "scope": manifest["scope"], "arms": {}}
    lines = [
        "# CQLLM 全量两组测试结果",
        "",
        manifest["scope"],
        "",
        "每组分母为全部 298 条需求；失败不删出分母。首轮与最多两轮后的编译分别统计。",
        "",
        "| 组别 | 首轮编译通过 | 最终编译通过 | 执行通过 | 调用记录 | 已知输入 token | 已知输出 token | 用量未知调用 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in manifest["arms"]:
        tasks = [r for r in rows if r["arm"] == arm]
        calls = [r for r in ledger if r["arm"] == arm]
        counts = {
            key: sum(r[key] for r in tasks)
            for key in ("first_compile_pass", "final_compile_pass", "execution_pass")
        }
        metrics = {
            "tasks": len(tasks),
            **counts,
            "generation_statuses": dict(Counter(r["generation_status"] for r in tasks)),
            "execution_statuses": dict(Counter(r["execution_status"] for r in tasks)),
            "calls": len(calls),
            "known_input_tokens": sum(r["input_tokens"] or 0 for r in calls),
            "known_output_tokens": sum(r["output_tokens"] or 0 for r in calls),
            "unknown_usage_calls": sum(
                r["input_tokens"] is None or r["output_tokens"] is None for r in calls
            ),
        }
        summary["arms"][arm] = metrics
        values = [
            f"{counts[k]}/{len(tasks)} ({counts[k] / len(tasks):.2%})" for k in counts
        ]
        lines.append(
            f"| {arm} | "
            + " | ".join(values)
            + f" | {len(calls)} | {metrics['known_input_tokens']} | {metrics['known_output_tokens']} | {metrics['unknown_usage_calls']} |"
        )
        save(
            output / f"{arm}-failure-statuses.json",
            {
                "generation": metrics["generation_statuses"],
                "execution": metrics["execution_statuses"],
                "failures": [
                    r
                    for r in tasks
                    if r["generation_status"] != "compiled"
                    or r["execution_status"] != "executed"
                ],
            },
        )
    lines.extend(
        [
            "",
            "编译成功和执行成功仅证明规则可运行；缺少独立定位与正负例标准答案，语义正确率不评分。",
            "本轮使用平台模型、检索和 CodeQL 适配器，尚未覆盖依赖真实项目源码与证据的完整 Rule8 工作流。",
            "",
            "论文 Table 4：仅 RAG 216/298（72.48%），LoRA+RAG 181/321（56.39%），仅 LoRA 71/321（22.12%）。",
            "论文各配置输出分母、模型和协议不同，不能将本轮编译/执行率直接视为论文正确率或等条件复现。",
            "",
            "附件：[逐任务表](tasks.csv)、[调用账本](resource-ledger.csv)、[机器汇总](summary.json)。",
            "",
        ]
    )
    save(output / "summary.json", summary)
    (output / "report.md").write_text("\n".join(lines))
    save(
        output / "checksums.json",
        {
            p.name: sha(p)
            for p in output.iterdir()
            if p.is_file() and p.name != "checksums.json"
        },
    )
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    export(args.output.resolve(), args.report.resolve())


if __name__ == "__main__":
    main()
