"""Report uniform full run and explicit project-level retests without cherry-picking."""

import argparse
from pathlib import Path

from scripts.benchmarks.realvuln_compare import positive_ids, read, validate_inputs
from scripts.benchmarks.realvuln_prepare import save
from scripts.benchmarks.realvuln_score import ARMS, metrics

RETESTS = (
    "realvuln-owasp-web-playground",
    "realvuln-pygoat",
    "realvuln-python-app",
    "realvuln-python-insecure-app",
)


def cards(root, projects, arm):
    return [read(root / "scores" / project / f"{arm}.json") for project in projects]


def row(label, result):
    return f"| {label} | {result['tp']} | {result['fp']} | {result['fn']} | {100 * result['precision']:.2f}% | {100 * result['recall']:.2f}% | {100 * result['f3']:.2f} |"


def build(before, full, retest, recovery=None):
    projects = validate_inputs(before, full)
    validate_inputs(full, retest)
    if not read(full / "scores/summary.json")["experiment_finished"]:
        raise RuntimeError("Uniform full run is unfinished")
    supplemental = list(RETESTS)
    origins = {p: retest for p in RETESTS}
    if recovery:
        validate_inputs(full, recovery)
        for p in (
            "realvuln-pygoat",
            "realvuln-python-app",
            "realvuln-python-insecure-app",
            "realvuln-vulnpy",
            "realvuln-vulpy",
        ):
            origins[p] = recovery
            if p not in supplemental:
                supplemental.append(p)
    for project in supplemental:
        if not (origins[project] / "system" / project / "result.json").exists():
            raise RuntimeError(f"Retest unfinished: {project}")
    uniform = read(full / "scores/summary.json")
    combined = {}
    provenance = {p: str(origins.get(p, full)) for p in projects}
    for arm in ARMS:
        combined[arm] = metrics(
            [read(Path(provenance[p]) / "scores" / p / f"{arm}.json") for p in projects]
        )
        if combined[arm]["tp"] + combined[arm]["fn"] != 676:
            raise RuntimeError("Full gold denominator changed")
    subset_metrics = {
        label: {arm: metrics(cards(root, RETESTS, arm)) for arm in ARMS}
        for label, root in (
            ("initial", before),
            ("uniform_v2", full),
            ("retest_v3", retest),
        )
    }
    lines = [
        "# RealVuln 修复后测试与补测",
        "",
        "2026-10-13。相同 26 个固定源码快照、676 条漏洞和 120 个陷阱。先完成统一 v2 全量实验，再以 v3 补测预先指定的四项目；v3 只修正证据拒绝被误算作无进展的问题，模型和提示版本保持不变。断网恢复后另接续五项目，与首次补测重合三项目，共六个项目采用补测结果。",
        "",
        "下列综合 supported 是系统证据门通过的 AI 判断。FP 为未匹配标注的输出，未独立利用验证；未决与扫描失败均保留。",
        "",
        "| 结果口径 | TP | FP | FN | Precision | Recall | F3 /100 |",
        "|---|---:|---:|---:|---:|---:|---:|",
        row("单 CodeQL（本轮实际重扫）", uniform["arms"]["codeql"]),
        row(
            "修复前综合 supported",
            read(before / "scores/summary.json")["arms"]["system_supported"],
        ),
        row(
            "统一 v2 全量 supported，包含断网失败", uniform["arms"]["system_supported"]
        ),
        row(
            f"{26 - len(supplemental)} 个 v2 项目＋{len(supplemental)} 个 v3 补测 supported",
            combined["system_supported"],
        ),
        row("增量汇总 retained，含所有未决", combined["system_retained"]),
        row("增量汇总原始候选并集", combined["raw_union"]),
        "",
        "增量汇总属于有明确来源的增量评估，不能称为统一 v3 全 26 项目重跑；按预先指定的整个项目替换输出，没有按漏洞标注择优拼接候选。补测 CodeQL 复用通过快照、版本与套件核验的成功基线，没有重复扫描。",
        "",
        "| 补测项目 | v2 TP/FP/F3 | v3 TP/FP/F3 | v2→v3 未决 | v3 复核停止原因 |",
        "|---|---:|---:|---:|---|",
    ]
    for project in supplemental:
        selected = origins[project]
        a, b = [
            cards(root, [project], "system_supported")[0] for root in (full, selected)
        ]
        results = [
            read(root / "system" / project / "result.json") for root in (full, selected)
        ]
        review = read(selected / "system" / project / "review.json")["stage"]
        lines.append(
            f"| {project} | {a['tp']}/{a['fp']}/{100 * a['f3']:.2f} | {b['tp']}/{b['fp']}/{100 * b['f3']:.2f} | {results[0]['unresolved_candidates']}→{results[1]['unresolved_candidates']} | {review['result'].get('stop_reason')} |"
        )
    coverage = {"inspected": 0, "eligible": 0, "unresolved": 0}
    for project in projects:
        result = read(Path(provenance[project]) / "system" / project / "result.json")
        c = result.get("scout_coverage", {})
        coverage["inspected"] += c.get(
            "inspected_eligible_windows", c.get("inspected_windows", 0)
        )
        coverage["eligible"] += c.get("eligible_windows", 0)
        coverage["unresolved"] += result.get("unresolved_candidates", 0)
    usage = {}
    for label, root, selected in (
        ("uniform_v2", full, projects),
        ("retest_v3", retest, RETESTS),
    ):
        usage[label] = {
            key: sum(
                read(root / "system" / p / f"{kind}.json")["stage"]["usage"].get(key, 0)
                or 0
                for p in selected
                for kind in ("scout", "review")
            )
            for key in ("calls", "input_tokens", "output_tokens")
        }
    if recovery:
        usage["recovery"] = {
            key: sum(
                read(recovery / "system" / p / "result.json")
                .get(f"{kind}_usage", {})
                .get(key, 0)
                or 0
                for p in origins
                if origins[p] == recovery
                for kind in ("scout", "review")
            )
            for key in ("calls", "input_tokens", "output_tokens")
        }
    lines.extend(
        [
            "",
            f"组合范围的初审覆盖 {coverage['inspected']}/{coverage['eligible']} 个可审窗口，未决候选 {coverage['unresolved']}。已检查窗口不等于每个安全任务或业务流程已得到证明，第三方延期另见原报告。",
            "",
            f"真实调用账本：v2 {usage['uniform_v2']}；四项目首次补测 {usage['retest_v3']}；再次网络恢复接续 {usage.get('recovery', {})}。补测成本另计，没有用复用输出冒充新增调用；缺失 usage 的记录仍明确标为未知。",
            "",
            "## 与作者保存输出比较",
            "",
            "相同标注下重评分作者已有结果，没有重新运行竞品。",
            "",
            "| 作者输出 | TP | FP | FN | Precision | Recall | F3 /100 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, result in uniform["author_rescored"].items():
        lines.append(row(name, result))
    lines.extend(
        [
            "",
            "## 解释与限制",
            "",
            "阶段总预算修复扩大了实际调查范围，但证据未决、多 CWE 分类和业务安全要求仍限制确认；召回与误报必须一起报告。断网失败不作为能力结论，原失败历史仍保留。模型随机波动也会影响新旧差异，本次没有完整机制消融；这些靶场已经用于诊断与调优，不能称为新的独立盲测。",
            "",
            "[统一全量报告](realvuln-20261013-progress-v2-results.md) · [修复前后逐项目对比](realvuln-20261013-progress-v2-comparison.md) · [补测协议](../experiments/realvuln-20261013-progress-v3-retest-protocol.md)",
            "",
        ]
    )
    overlap = gained = lost = 0
    for project in projects:
        root = Path(provenance[project])
        static = positive_ids(cards(root, [project], "codeql")[0])
        supported = positive_ids(cards(root, [project], "system_supported")[0])
        overlap += len(static & supported)
        gained += len(supported - static)
        lost += len(static - supported)
    final = combined["system_supported"]
    lines.extend(
        [
            "",
            "## 最终能力结论",
            "",
            f"当前平台适合作为扩展发现范围、提供证据和辅助人工复核的审计系统。通过证据门的输出命中 {final['tp']}/676 条漏洞，召回 {100 * final['recall']:.2f}%，F3 {100 * final['f3']:.2f}；精确率 {100 * final['precision']:.2f}%，仍不能替代人工确认或作为自动判定项目安全的依据。",
            "",
            f"与 CodeQL 的 106 条正确命中相比，系统保留其中 {overlap} 条、额外命中 {gained} 条，仍遗漏其中 {lost} 条。总发现数量不如 CodeQL 的问题已改善，但确认链路仍有信息损失。",
            "",
            "F3 = 10TP / (10TP + 9FN + FP)，更重视召回。当前 F3 与作者保存的 Sonnet、Gemini 输出接近，但本系统精确率明显更低，不能据此宣称整体能力持平或超过它们；与 Kolega 的召回和 F3 仍有较大差距。保留所有未决的 retained 分数代表待复核范围，不是最终确认能力。",
            "",
            f"初审窗口覆盖从 112/1168（9.59%）提高到 {coverage['inspected']}/{coverage['eligible']}（{100 * coverage['inspected'] / coverage['eligible']:.2f}%）。仍有 {coverage['eligible'] - coverage['inspected']} 个窗口没有有效检查结果、{coverage['unresolved']} 个候选未决；窗口覆盖不等于漏洞召回或业务流程证明覆盖。",
            "",
            "下一轮改进优先级：1）用 AST 和框架路由、导入关系补全跨文件控制证据，针对未决候选定位证据缺口；2）规范多 CWE 输出、去重及精确位置，按误报类别评估；3）明确业务安全要求后验证授权和业务逻辑；4）加强进程中断检查点恢复与瞬时网络错误恢复。用新项目盲测验证收益，避免继续仅在本批靶场调优。",
            "",
            "## 最终逐项目结果",
            "",
            "| 项目 | CodeQL TP/FP/F3 | 系统 supported TP/FP/F3 | 可审窗口 | 未决 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for project in projects:
        root = Path(provenance[project])
        a, b = [
            cards(root, [project], arm)[0] for arm in ("codeql", "system_supported")
        ]
        result = read(root / "system" / project / "result.json")
        c = result["scout_coverage"]
        lines.append(
            f"| {project} | {a['tp']}/{a['fp']}/{100 * a['f3']:.2f} | {b['tp']}/{b['fp']}/{100 * b['f3']:.2f} | {c.get('inspected_eligible_windows', c['inspected_windows'])}/{c.get('eligible_windows', c['planned_windows'])} | {result['unresolved_candidates']} |"
        )
    return "\n".join(lines), {
        "provenance": provenance,
        "combined_arms": combined,
        "subset_metrics": subset_metrics,
        "coverage": coverage,
        "usage": usage,
        "uniform_full_run": str(full),
        "retest_run": str(retest),
        "uniform_v3_full_run": False,
        "codeql_overlap": overlap,
        "additional_gold_hits": gained,
        "lost_codeql_gold_hits": lost,
    }


def main():
    parser = argparse.ArgumentParser()
    for name in ("before", "full", "retest", "report"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--recovery", type=Path)
    args = parser.parse_args()
    body, data = build(
        args.before.resolve(),
        args.full.resolve(),
        args.retest.resolve(),
        args.recovery.resolve() if args.recovery else None,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(body)
    save(args.retest / "incremental-report-data.json", data)


if __name__ == "__main__":
    main()
