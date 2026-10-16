"""Paired completed RealVuln experiments with identical inputs and gold labels."""

import argparse
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def positive_ids(card):
    return {
        r["ground_truth_id"] for r in card["details"] if r["classification"] == "TP"
    }


def validate_inputs(before, after):
    left, right = [read(root / "dataset.json") for root in (before, after)]
    # Bytecode caches are generated evaluator runtime artifacts, not inputs.
    for dataset in (left, right):
        dataset["gold_sha256"] = {
            k: v
            for k, v in dataset["gold_sha256"].items()
            if "__pycache__" not in Path(k).parts and not k.endswith(".pyc")
        }
    for key in ("manifest", "gold_sha256", "paper_gold_counts"):
        if left[key] != right[key]:
            raise RuntimeError(f"Paired evaluation inputs changed: {key}")
    for project in left["manifest"]["repos"]:
        receipts = [
            read(root / "acquisition" / f"{project}.json") for root in (before, after)
        ]
        if receipts[0]["snapshot"] != receipts[1]["snapshot"]:
            raise RuntimeError(f"Source changed: {project}")
    return list(left["manifest"]["repos"])


def compare(before, after):
    projects = validate_inputs(before, after)
    summaries = [read(root / "scores/summary.json") for root in (before, after)]
    if not all(r["experiment_finished"] for r in summaries):
        raise RuntimeError("Full comparison requires completed experiments")
    lines = [
        "# RealVuln 修复前后全量对比",
        "",
        "26 个项目采用相同源码快照、676 个漏洞标注和评分器。F3 按 0–100 展示；候选支持仍是系统证据门通过结果。",
        "",
        "| 链路 | 修复前 TP/FP/FN | 修复后 TP/FP/FN | 前 F3 | 后 F3 |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm in summaries[0]["arms"]:
        a, b = [s["arms"][arm] for s in summaries]
        lines.append(
            f"| {arm} | {a['tp']}/{a['fp']}/{a['fn']} | {b['tp']}/{b['fp']}/{b['fn']} | {a['f3'] * 100:.2f} | {b['f3'] * 100:.2f} |"
        )
    lines.extend(
        [
            "",
            "| 项目 | 前 TP/FP | 后 TP/FP | 前 F3 | 后 F3 | 新命中/丢失 | 前窗口 | 后窗口 | 后未决 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    totals = [
        {
            "inspected": 0,
            "eligible": 0,
            "unresolved": 0,
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        }
        for _ in range(2)
    ]
    for project in projects:
        cards = [
            read(root / "scores" / project / "system_supported.json")
            for root in (before, after)
        ]
        results = [
            read(root / "system" / project / "result.json")
            if (root / "system" / project / "result.json").exists()
            else {}
            for root in (before, after)
        ]
        coverages = [r.get("scout_coverage", {}) for r in results]
        ids = [positive_ids(r) for r in cards]
        for index, result in enumerate(results):
            coverage = coverages[index]
            totals[index]["inspected"] += coverage.get(
                "inspected_eligible_windows", coverage.get("inspected_windows", 0)
            )
            totals[index]["eligible"] += coverage.get(
                "eligible_windows", coverage.get("planned_windows", 0)
            )
            totals[index]["unresolved"] += result.get("unresolved_candidates", 0)
            for kind in ("scout", "review"):
                for key in ("calls", "input_tokens", "output_tokens"):
                    totals[index][key] += (
                        result.get(f"{kind}_usage", {}).get(key, 0) or 0
                    )
        a, b = cards
        windows = [
            f"{c.get('inspected_eligible_windows', c.get('inspected_windows', 0))}/{c.get('eligible_windows', c.get('planned_windows', 0))}"
            for c in coverages
        ]
        lines.append(
            f"| {project} | {a['tp']}/{a['fp']} | {b['tp']}/{b['fp']} | {a['f3'] * 100:.2f} | {b['f3'] * 100:.2f} | {len(ids[1] - ids[0])}/{len(ids[0] - ids[1])} | {windows[0]} | {windows[1]} | {results[1].get('unresolved_candidates', '未评估')} |"
        )
    lines.extend(
        ["", "## 执行与覆盖", "", "| 指标 | 修复前 | 修复后 |", "|---|---:|---:|"]
    )
    for key in totals[0]:
        lines.append(f"| {key} | {totals[0][key]} | {totals[1][key]} |")
    lines.extend(
        [
            "",
            "窗口已检查不表示所有安全任务都已证明；第三方延期、失败和未决范围见两轮原始报告。没有 usage 的请求不计作已知 token，原账本保留未知用量标记。模型与服务环境的波动仍会影响结果，不能把全部差异归因于单一代码修复。",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    body = compare(args.before.resolve(), args.after.resolve())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(body)


if __name__ == "__main__":
    main()
