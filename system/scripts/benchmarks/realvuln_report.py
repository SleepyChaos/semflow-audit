"""Build a reviewable full-corpus report only after all targets were attempted."""

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

from scripts.benchmarks.realvuln_prepare import save


def read(path):
    return json.loads(path.read_text())


def metric_row(label, row):
    return (
        f"| {label} | {row['tp']} | {row['fp']} | {row['fn']} | "
        f"{row['precision'] * 100:.2f}% | {row['recall'] * 100:.2f}% | "
        f"{row['f1'] * 100:.2f} | {row['f3'] * 100:.2f} |"
    )


def matched_ids(card):
    return {
        d["ground_truth_id"] for d in card["details"] if d["classification"] == "TP"
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    summary = read(output / "scores/summary.json")
    if not summary["experiment_finished"]:
        raise RuntimeError(
            "Cannot publish an unfinished progress score as a final report"
        )
    dataset = read(output / "dataset.json")
    config = read(output / "config.json")
    policy = config.get("model_policies", {}).get(
        "review", config.get("model_policy", {})
    )
    experiment_path = (
        output.relative_to(Path.cwd()) if output.is_relative_to(Path.cwd()) else output
    )
    protocol = (
        "realvuln-20261013-progress-v2-protocol.md"
        if "model_policies" in config
        else "realvuln-20261013-protocol.md"
    )
    historical_timing_note = (
        "两个粗筛阶段因用户中断沿用原 ID 恢复；wall_seconds 只含恢复段，时间合计为下界。"
        if (output / "attempts/00-environment-path-error").exists()
        else "本轮模型阶段墙钟时间按各阶段完整运行记录统计。"
    )
    static_rows, system_rows, stages, project_rows = [], [], [], []
    for project in dataset["manifest"]["repos"]:
        static = read(output / "static" / project / "result.json")
        directory = output / "system" / project
        result_path = directory / "result.json"
        result = read(
            result_path if result_path.exists() else directory / "runner-error.json"
        )
        static_rows.append(static)
        system_rows.append(result)
        for kind in ("scout", "review"):
            path = directory / f"{kind}.json"
            if path.exists():
                stages.append({"project": project, "kind": kind, **read(path)["stage"]})
        cards = {
            arm: read(output / "scores" / project / f"{arm}.json")
            for arm in summary["arms"]
        }
        baseline_ids = matched_ids(cards["codeql"])
        supported_ids = matched_ids(cards["system_supported"])
        coverage = result.get("scout_coverage", {})
        project_rows.append(
            {
                "project": project,
                "static_tp": cards["codeql"]["tp"],
                "static_fp": cards["codeql"]["fp"],
                "system_tp": cards["system_supported"]["tp"],
                "system_fp": cards["system_supported"]["fp"],
                "retained_tp": cards["system_retained"]["tp"],
                "retained_fp": cards["system_retained"]["fp"],
                "gained_ids": sorted(supported_ids - baseline_ids),
                "lost_ids": sorted(baseline_ids - supported_ids),
                "inspected_windows": coverage.get("inspected_windows", 0),
                "eligible_windows": coverage.get(
                    "eligible_windows", coverage.get("planned_windows", 0)
                ),
                "stop_reason": coverage.get("stop_reason"),
                "status": result["status"],
                "static_status": static["status"],
                "review_coverage": result.get("review_coverage"),
                "unresolved": result.get("unresolved_candidates", 0),
            }
        )
    totals = {
        key: sum(r[key] for r in project_rows)
        for key in ("inspected_windows", "eligible_windows", "unresolved")
    }
    usage = {
        key: sum(s.get("usage", {}).get(key, 0) or 0 for s in stages)
        for key in ("calls", "input_tokens", "output_tokens")
    }
    reasons = Counter(r["stop_reason"] for r in project_rows)
    errors = [
        {
            "project": s["project"],
            "kind": s["kind"],
            "status": s["status"],
            "error": s.get("error"),
        }
        for s in stages
        if s["status"] != "completed"
    ]
    batch_errors = Counter(
        b.get("code", "validation_rejected")
        for s in stages
        if s["kind"] == "review"
        for b in s["result"].get("batches", [])
        if b["status"] in {"incomplete", "partial"}
    )
    gains = sum(len(r["gained_ids"]) for r in project_rows)
    losses = sum(len(r["lost_ids"]) for r in project_rows)
    record = {
        "metrics": summary,
        "project_comparison": project_rows,
        "usage": usage,
        "coverage": totals,
        "stop_reasons": dict(reasons),
        "stage_errors": errors,
        "review_incomplete_reasons": dict(batch_errors),
        "known_gold_gains": gains,
        "known_gold_losses": losses,
    }
    save(output / "report-data.json", record)
    arm = summary["arms"]
    delta = {
        key: arm["system_supported"][key] - arm["codeql"][key]
        for key in ("tp", "fp", "recall", "precision", "f1", "f3")
    }
    lines = [
        "# RealVuln 论文全 26 项目：单 CodeQL 与综合审计系统",
        "",
        "日期：2026-10-13。全部项目已尝试；默认预算下的部分覆盖和未决结果单独保留。",
        "",
        (
            f"综合系统相对单 CodeQL：TP {delta['tp']:+d}，FP {delta['fp']:+d}，"
            f"Recall {delta['recall'] * 100:+.2f} 个百分点，Precision {delta['precision'] * 100:+.2f} 个百分点，"
            f"F3 {delta['f3'] * 100:+.2f}。此结果仅代表本轮冻结实现、模型和预算。"
        ),
        "",
        "## 两条链路的主结果",
        "",
        "分母为论文全部 676 条漏洞；另有 120 条 FP traps。使用官方 strict micro 评分。",
        "",
        "| 链路 | TP | FP | FN | Precision | Recall | F1 /100 | F3 /100 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        metric_row("单 CodeQL", arm["codeql"]),
        metric_row("综合系统：AI 支持输出", arm["system_supported"]),
        "",
        (
            f"综合系统主结果取 Review v{config['review_version']} 的 `supported`，是经过产品结构/证据门的 AI 分类，"
            "不是本次新增的独立人工确认。未决、证据不足和未检查候选仍保留在产物中，未默认判为误报。"
        ),
        "",
        "| 辅助口径 | TP | FP | FN | Precision | Recall | F1 /100 | F3 /100 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        metric_row("综合系统：保留所有未决，仅排除已验证误报", arm["system_retained"]),
        metric_row("复核前 CodeQL＋粗筛原始并集", arm["raw_union"]),
        "",
        (
            f"按黄金标签 ID 配对，最终支持输出新增命中 {gains} 条、失去基线命中 {losses} 条；"
            "失去支持可能来自明确排除、证据不足或尚未复核，需要结合每项目记录分析，不能一概称成功过滤。"
        ),
        "",
        "## 与论文作者结果比较",
        "",
        (
            "以下是作者保存输出在本轮相同 26 项目、676 标签上的重评分；没有重新运行这些竞品。"
            "传统静态工具、Kolega、Sonnet 和 Gemini 的重评分复现论文主表至显示精度附近。"
        ),
        "",
        "| 作者已有输出 | TP | FP | FN | Precision | Recall | F1 /100 | F3 /100 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in summary["author_rescored"].items():
        lines.append(metric_row(name, row))
    lines.extend(
        [
            "",
            (
                "论文来源：[RealVuln arXiv v1](https://arxiv.org/abs/2604.13764)，Table 2/4。"
                "本轮模型、架构和预算与作者不同，比较的是完整系统表现，不能单独归因到某个机制。"
            ),
            "",
            "## 完成状态、预算和时间",
            "",
            (
                f"- CodeQL 成功 {sum(r['status'] == 'succeeded' for r in static_rows)}/26；"
                f"综合阶段结果状态：{dict(Counter(r['status'] for r in system_rows))}。"
            ),
            (
                f"- Scout/Review 阶段状态：{dict(Counter(s['status'] for s in stages))}；"
                f"覆盖状态与阶段状态分别记录。未决候选 {totals['unresolved']} 个。"
            ),
            (
                f"- 独立粗筛检查 {totals['inspected_windows']}/{totals['eligible_windows']} 个非第三方可选窗口；"
                f"停止原因：{dict(reasons)}。不能称为所有文件/业务流程均检查完毕。"
            ),
            (
                f"- 实际模型调用 {usage['calls']} 次，输入 {usage['input_tokens']} tokens，输出 {usage['output_tokens']} tokens。"
                "服务未提供可靠统一单价，本报告不虚构美元成本。"
            ),
            (
                f"- CodeQL 抽取＋查询时间合计 {sum(r.get('wall_seconds', 0) for r in static_rows):.1f} 秒；"
                f"模型阶段合计 {sum(read(output / 'system' / s['project'] / (s['kind'] + '.json'))['wall_seconds'] for s in stages):.1f} 秒。"
            ),
            (
                f"- 每项目顺序链路中位数 {statistics.median(r.get('sequential_chain_seconds', 0) for r in system_rows):.1f} 秒；"
                "项目并发 2，static 输出共享，以上不是产品双引擎并发端到端延迟。"
                + historical_timing_note
            ),
            "",
            f"复核未完成批次原因计数：{dict(batch_errors)}。非完成阶段错误详见本地 `report-data.json`。",
            "",
            "## 全部项目逐项结果",
            "",
            "TP/FP 为官方匹配后的计数；多 CWE 告警按作者 parser 方式展开。",
            "",
            "| 项目 | CodeQL TP/FP | 综合支持 TP/FP | 保留未决 TP/FP | 粗筛窗口 已检查/可选 | 未决 | 状态 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in project_rows:
        lines.append(
            f"| {row['project']} | {row['static_tp']}/{row['static_fp']} | "
            f"{row['system_tp']}/{row['system_fp']} | {row['retained_tp']}/{row['retained_fp']} | "
            f"{row['inspected_windows']}/{row['eligible_windows']} | {row['unresolved']} | {row['status']} |"
        )
    lines.extend(
        [
            "",
            "## 版本、边界和复现",
            "",
            "- 评分统一规范化 CWE 前导零；源码、标注与模型产物分离。",
            f"- CodeQL {config['codeql_cli']}，Python 查询包 {config['packs']['python']['pack']}，标准 code-scanning 套件。",
            (
                f"- 模型 `{policy['model']}`，Scout v{config['scout_version']} / Review v{config['review_version']}；执行模式 {policy.get('execution_mode', 'bounded')}；调用、token、时间预算（0 表示无阶段总上限） "
                f"{policy['max_calls']} / {policy['max_tokens']} / {policy['max_seconds']} 秒。"
            ),
            (
                "- 标注来源官方 GitHub 历史 `55350cdc0f0f7db85d1f0b97649df07e6d63c665`；"
                "全部目标 commit 与官方 v1.0 清单一致。HF 无法连接，未验证 HF 字节身份。"
                "后来的 GitHub v1.0 标注增至 697，本轮未混入新增标签。"
            ),
            (
                "- 模型使用独立源码目录，evaluator-only 标签、描述、PoC 和作者结果没有进入模型输入或 RAG。"
                "目标仓库原有文档/注释保留，Flask 曾用于开发校准，不能称整个数据集独立盲测。"
            ),
            (
                "- 这是生产适配器、服务、LangGraph、数据库和真实模型的核心链路评测；研究注册桥绕过 ZIP 上传/GUI。"
                "OWASP Web Playground 3066 文件超过当前上传文件数限制。未评估修复与新规则生成。"
            ),
            (
                "- 执行期间冻结实现保持不变。源码/实现哈希、阶段 ID、实际响应、SARIF、失败历史保存在本地忽略目录。"
            ),
            (
                "- 评分用官方文件/CWE/±10 行 matcher，每条 GT 只消耗一次；重复告警计额外 FP。"
                "未知 CWE 保留为未匹配 FP。标签可能不完备，未匹配 FP 不等于已用利用测试证明安全。"
            ),
            "",
            f"详细协议：[{protocol}](../experiments/{protocol})。",
            "",
            (
                f"原始与机器结果目录：`{experiment_path}/`；主汇总 `scores/summary.json`，"
                "逐项匹配 `scores/<project>/`，配对 gains/losses、错误与预算 `report-data.json`。"
            ),
            "",
            "从仓库根目录重评分（不会新增模型调用）：",
            "",
            "```sh",
            "PYTHONPATH=system system/.venv/bin/python -m scripts.benchmarks.realvuln_score \\",
            f"  --output {experiment_path}",
            "PYTHONPATH=system system/.venv/bin/python -m scripts.benchmarks.realvuln_report \\",
            f"  --output {experiment_path} \\",
            f"  --report {args.report}",
            "```",
            "",
        ]
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines))
    print(
        json.dumps(
            {"report": str(args.report.resolve()), "usage": usage, "delta": delta},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
