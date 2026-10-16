"""Validate full six-arm receipts and render a paired capability report."""

import argparse
import csv
from collections import Counter
from pathlib import Path

from scripts.benchmarks.realvuln_ablation_diagnostics import (
    diagnose,
    discovery_projects,
)
from scripts.benchmarks.realvuln_ablation_io import read
from scripts.benchmarks.realvuln_ablation_report import report
from scripts.benchmarks.realvuln_ablation_static_cost import export as static_cost
from scripts.benchmarks.realvuln_ablation_validation import validate, validate_sources
from scripts.benchmarks.realvuln_prepare import save


def finish(base, output):
    validate_sources(base, output)
    identities = validate(output)
    static_summary = static_cost(base, output)
    summary = report(base, output)
    diagnostics = diagnose(output)
    discovery_projects(output)
    data = read(output / "formal-summary.json")
    if not data["finished"]:
        raise RuntimeError("Full metrics pending")
    if (
        len(data["new_review_stage_ids"]) != 72
        or len(data["adopted_review_stage_ids"]) != 78
    ):
        raise RuntimeError("New/reused review stage identity count differs")
    rows = {r["group"]: r for r in summary}
    adopted = {}
    for group in "ABCDEF":
        r = rows[group]
        adopted[group] = {
            "calls": r.get("calls_reused", 0)
            if group in "ABC"
            else r["review_calls_new"]
            + r["review_calls_reused"]
            + r["upstream_calls_reused"],
            "input_tokens_known": r.get("input_tokens_known", 0)
            if group in "ABC"
            else r["review_input_tokens_known"] + r["upstream_input_tokens_known"],
            "output_tokens_known": r.get("output_tokens_known", 0)
            if group in "ABC"
            else r["review_output_tokens_known"] + r["upstream_output_tokens_known"],
            "unknown_usage_calls": r["unknown_usage_calls"]
            + r.get("upstream_unknown_usage_calls", 0),
        }
    accumulated = {
        key: data["historical_stage_resources"][key]
        + data["new_execution_resources"][key]
        for key in ("calls", "input_tokens", "output_tokens", "unknown_usage_calls")
    }
    probe_path = output / "provider-recovery-probe.json"
    probe_cost = {}
    if probe_path.exists():
        probe = read(probe_path)
        usage = probe.get("usage") or {}
        probe_cost = {
            "calls": 1,
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "unknown_usage_calls": int(not usage),
        }
        accumulated = {k: v + probe_cost[k] for k, v in accumulated.items()}
    save(
        output / "resources-comparison.json",
        {
            "adopted_per_group": adopted,
            "new_execution": data["new_execution_resources"],
            "infrastructure_recovery_probe": probe_cost,
            "all_attempts_cumulative": accumulated,
            "static": static_summary,
            "do_not_sum_shared_upstream_across_groups": True,
        },
    )
    ledger_path = output / "all-attempt-stage-ledger.json"
    historical_ledger = output / "historical-incremental/all-attempt-stage-ledger.json"
    if not historical_ledger.exists():
        save(historical_ledger, read(ledger_path))
    ledger = read(historical_ledger)
    for path in output.glob("arms/*/system/*/review.json"):
        record = read(path)
        ledger.setdefault(
            record["stage_id"],
            {
                "stage": record["stage"],
                "receipt": str(path),
                "wall_seconds": record["wall_seconds"],
            },
        )
    save(ledger_path, ledger)
    names = {
        "A": "CodeQL",
        "B": "Scout",
        "C": "CodeQL＋Scout",
        "D": "CodeQL＋Review",
        "E": "Scout＋Review",
        "F": "CodeQL＋Scout＋Review",
    }
    overlap = list(csv.DictReader((output / "discovery-overlap.csv").open()))
    gold_review = list(csv.DictReader((output / "review-gold-transitions.csv").open()))
    a_gold = {
        (r["project_id"], r["gold_id"])
        for r in overlap
        if r["codeql_independent_hit"] == "True"
    }
    f_gold = {
        (r["project_id"], r["gold_id"])
        for r in gold_review
        if r["group"] == "F" and r["after_supported_hit"] == "True"
    }
    if len(a_gold) != rows["A"]["tp"] or len(f_gold) != rows["F"]["tp"]:
        raise RuntimeError("CodeQL/system paired gold counts differ")
    source = output / "ablation-results.md"
    historical = source.read_text()
    # Keep the fully documented historical reconstruction, separate from the new
    # independent results. Never rewrite its 352/359 result as uniform v3.
    if not (output / "historical-incremental/ablation-results.md").exists():
        (output / "historical-incremental/ablation-results.md").write_text(historical)
    lines = [
        "# RealVuln 六组消融补全结果",
        "",
        "2026-10-14。六组均覆盖固定26项目、676漏洞、120陷阱。A/B/C复用冻结发现输入并独立评分；D/E各26项目独立Review12；F新增20项统一v3复审，复用6项v3结果。上游Scout保留已冻结的增量候选与继承历史，统一的是复审实现，不称全链v3全量重跑。",
        "",
        "supported是实际证据门通过的模型判断，不是人工确认或利用成功。FP为未匹配基准标签，未逐项独立验证。所有未决和失败保留。",
        "F3 = 10TP / (10TP + 9FN + FP)，更重视召回。精确率提高不代表F3提高，应同时检查丢失命中和未匹配输出的变化。",
        "",
        "| 组别 | 链路 | TP | FP | FN | Precision (%) | Recall (%) | F1 /100 | F3 /100 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for group in "ABCDEF":
        row = rows[group]
        cells = [str(row[k]) for k in ("tp", "fp", "fn")] + [
            f"{100 * row[k]:.2f}" for k in ("precision", "recall", "f1", "f3")
        ]
        lines.append(f"| {group} | {names[group]} | " + " | ".join(cells) + " |")
    lines.extend(
        [
            "",
            f"![六组Precision、Recall、F3及TP/FP对照]({output / 'ablation-comparison.png'})",
            "",
        ]
    )
    lines.extend(
        [
            "",
            "## 模块收益与损失",
            "",
            "以下为本轮配对观察，每组仅一次运行，不称统计显著或新独立盲测。",
            "",
            "| 对照 | TP变化 | FP变化 | Precision百分点 | Recall百分点 | F3变化 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for left, right in (
        ("A", "C"),
        ("B", "C"),
        ("A", "D"),
        ("B", "E"),
        ("C", "F"),
        ("D", "F"),
        ("E", "F"),
        ("A", "F"),
    ):
        a, b = rows[left], rows[right]
        cells = [f"{b[k] - a[k]:+d}" for k in ("tp", "fp")] + [
            f"{100 * (b[k] - a[k]):+.2f}" for k in ("precision", "recall", "f3")
        ]
        lines.append(f"| {left}→{right} | " + " | ".join(cells) + " |")
    highest_f3 = max("ABCDEF", key=lambda g: rows[g]["f3"])
    reviewed_best = max("DEF", key=lambda g: rows[g]["f3"])
    precise_best = max("DEF", key=lambda g: rows[g]["precision"])
    lines.extend(
        [
            "",
            "本轮观察：",
            "",
            f"- 当前完整系统命中{rows['F']['tp']}/676，保留CodeQL独立命中的{len(a_gold & f_gold)}条，额外匹配{len(f_gold - a_gold)}条，仍未保留其中{len(a_gold - f_gold)}条。相对CodeQL，FP总数增加{rows['F']['fp'] - rows['A']['fp']}，不能宣称所有指标改善或误报总数下降。",
            f"- 发现端：加入Scout后，A→C新增净命中{rows['C']['tp'] - rows['A']['tp']}条，Recall增加{100 * (rows['C']['recall'] - rows['A']['recall']):.2f}个百分点；主要扩展来自Scout独有命中。CodeQL仍保留26条独立独有命中。",
            f"- 六组F3最高的是{highest_f3}（{names[highest_f3]}，{100 * rows[highest_f3]['f3']:.2f}）；仅比较复审输出，F3最高的是{reviewed_best}（{100 * rows[reviewed_best]['f3']:.2f}），Precision最高的是{precise_best}（{100 * rows[precise_best]['precision']:.2f}%）。",
            f"- 完整链路C→F：TP净变化{rows['F']['tp'] - rows['C']['tp']:+d}、FP净变化{rows['F']['fp'] - rows['C']['fp']:+d}、Precision变化{100 * (rows['F']['precision'] - rows['C']['precision']):+.2f}个百分点、Recall变化{100 * (rows['F']['recall'] - rows['C']['recall']):+.2f}个百分点、F3变化{100 * (rows['F']['f3'] - rows['C']['f3']):+.2f}。这说明发现结果和supported输出需要分别评价，未决仍应保留给后续取证。",
            "- 改进应先处理下方未决与证据门拒收原因、提升独立新项目发现覆盖，再验证复审的召回收益；不能仅按FP净减少数量判断Review质量。多CWE收敛与评分分配变化也贡献了分数变化。",
        ]
    )
    lines.extend(
        [
            "",
            "## 复审去向",
            "",
            "按金标分配和候选状态分别统计，未进入supported不默认排除。多CWE展开、CWE修订及顺序分配变化单独保留。历史F的FP净差551由336条原FP未进入supported与215条supported输出多CWE缩减／重新匹配净变化组成，后者不等于215次语义排除；详细原去向表单独保存。",
            "",
            "| 组别 | 原命中保留 | 原命中未保留 | 复审新增匹配 | 前后均遗漏 | 候选状态 |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for group in "DEF":
        cell = data["review_gold_transitions"][group]
        states = diagnostics[group]["candidate_states"]
        lines.append(
            f"| {group} | {cell.get('retained', 0)} | {cell.get('lost_from_supported', 0)} | {cell.get('gained_after_review', 0)} | {cell.get('missed_both', 0)} | {dict(states)} |"
        )
    lines.extend(["", "E组计划池923项，最终候选状态合计924项：VulPy复审批次a903960fc19bc235d15756ad保存了1条新的未验证会话伪造线索，候选c9c51f5a-208f-46b1-8720-707e2874e544保持pending，未进入原95项项目候选池。它不是恢复继承的历史pending，不进入supported的TP/FP成绩。", ""])
    lines.extend(
        [
            "",
            "### 原始评分条目进入复审的状态",
            "",
            "这些是多CWE展开后的原始TP/FP条目去向，不能与复审最终FP直接相减来计算语义排除。",
            "",
            "| 组别 | 原TP条目状态 | 原FP条目状态 | CWE修订候选 | 位置修订候选 |",
            "|---|---|---|---:|---:|",
        ]
    )
    for group in "DEF":
        d = diagnostics[group]
        entity_states = d["before_scored_entity_states"]
        lines.append(
            f"| {group} | {entity_states.get('TP', {})} | {entity_states.get('FP', {})} | {d['cwe_changed_candidates']} | {d['location_changed_candidates']} |"
        )
    lines.extend(["", "FP净变化按两部分核对：", ""])
    for before_group, after_group in (("A", "D"), ("B", "E"), ("C", "F")):
        states = diagnostics[after_group]["before_scored_entity_states"].get("FP", {})
        supported_before = states.get("supported", 0)
        not_supported = sum(v for k, v in states.items() if k != "supported")
        output_change = supported_before - rows[after_group]["fp"]
        if (
            not_supported + output_change
            != rows[before_group]["fp"] - rows[after_group]["fp"]
        ):
            raise RuntimeError(
                "FP transition accounting disagrees with aggregate score"
            )
        lines.append(
            f"- {before_group}→{after_group}：{not_supported}条原FP评分条目未进入supported；仍为supported的原FP条目与最终FP相差{output_change:+d}条。后者包含CWE收敛、去重、重新匹配及新输出变化，不能称为{output_change}次语义排除。"
        )
    lines.extend(["", "### 未决与实际取证", ""])
    for group in "DEF":
        d = diagnostics[group]
        top = Counter(d["rejected_unique_candidates_by_reason"]).most_common(3)
        lines.append(
            f"- {group}：成功／部分批次记录的工具观察 {d['actual_tools']}，其中复用 {d['reused_tool_observations']}；停止原因 {d['stop_reasons']}；证据门拒收主要原因（按候选去重，同一候选可涉及多种原因）{top}。"
        )
    lines.append(
        "已持久化的判断理由、缺失前提、拒收次数和逐项目状态见review-diagnostics.json及review-diagnostics-per-project.csv；未知与未执行均保留。阶段级trace只保留最后上下文，不能当作全阶段工具账本；以上按逐批次trace统计，失败批次可能缺失工具轨迹，分别有D4/E23/F29个incomplete批次未保存trace。这些记录不能证明完整工具执行次数，原模型响应产物另保留。"
    )
    lines.extend(
        [
            "",
            "## 发现交集、版本与资源",
            "",
            "独立A/B金标集合：CodeQL独有26、Scout独有309、共同80、共同遗漏261。独立并集415与C的416差1：PyGoat的pygoat-053受官方按顺序、金标一次分配规则影响。C的已分配416个TP按兼容来源分为CodeQL独有25、Scout独有309、共同兼容82，另遗漏260；此兼容分解不能当作独立A/B命中。discovery-overlap.csv保留两种口径和逐候选依据。",
            "",
            "实际复审提示摘要及执行政策已逐阶段核验，独立D/E候选池无跨组来源。模型、prompt、CodeQL、评分器、快照与阶段身份见stage-inventory.csv和formal-review-identity.json。公共知识库437块版本/摘要已登记，实际调用轨迹另保留，允许使用不等于确实使用。",
            "",
            f"本次新增72个复审阶段已知资源：{data['new_execution_resources']}。历史全部尝试按阶段ID去重：{data['historical_stage_resources']}。F复用的6阶段不计新增；E/F共享上游1819次Scout调用，不能跨组相加。unknown_usage_calls表示未知请求，不将缺失usage记为零成本。实际响应模型与未知响应数见身份清单。",
            "",
            f"历史与本次所有尝试累计：{accumulated}。CodeQL历史实际/复用/失败与耗时：{static_summary}。采用阶段、新执行和累计结果同时保存在resources-comparison.json。",
            "累计额外的1次调用、8输入token和1输出token来自E组PyGoat连接恢复探针，已在provider-recovery-probe.json单列。因此3614＋1973＋1＝5588；该探针不计入六组成绩或采用阶段成本。",
            "",
            "采用成本包含必要的继承Scout历史和最终选用复审；全部尝试保留失败及未选用版本。review-resources.csv区分新执行/复用及实际秒数，ablation-per-project.csv保留源码发现覆盖、状态和回执；阶段时间之和不代表GUI并发延迟。",
            "账户五小时限制后，E组PythonSSTI复用原阶段和候选池恢复。旧进程退出前没有持久化模型调用回执；该中断片段耗时未知，且无法排除未返回回执的在途请求。资源表明确标记此缺口，已知成本不能视为供应商账单精确总额。恢复过程和中断前数据库状态保存在attempts/process-interruption-1/。",
            "",
            f"复审阶段状态分布：{dict(Counter(i['status'] for i in identities))}；覆盖状态分布：{dict(Counter(str(i['coverage_status']) for i in identities))}。工作流completed不等于所有候选已获结论。",
            "",
            "## 结论边界与交付",
            "",
            "本实验补齐了Scout独立评分、D/E独立复审、F版本一致性、发现交集、逐候选/金标去向和实际资源。结合上表判断发现范围、精确率收益与召回损失，不能将预算与调度演进单独归因于某个模块。FP的绝对数量与比例须同时看；未决不当作安全。",
            "",
            "数据来自作者GitHub论文兼容提交55350cdc0f0f7db85d1f0b97649df07e6d63c665，未完成与HF v1.0.0逐字节核验，不能宣称HF身份完全一致。本批已参与调优，单次结果不能证明新项目泛化或系统独立自动确认能力。竞品沿用此前作者输出重评分，本轮未重新运行。Vul4Py/CQLLM和端到端修复按用户要求暂缓。",
            "",
            "本目录包含完整协议、六组总表与156行逐项目表、676行交集、三组逐候选和2028行金标去向（每组676）、阶段与知识身份、资源账本。历史增量352/359结果保存在historical-incremental/，没有冒充正式F。",
        ]
    )
    lines.extend(
        [
            "",
            "## 六组采用资源",
            "",
            "采用调用含共享上游与必要继承历史，不能将各组相加作为累计花费。新增调用仅指本次复审；静态调用不折算成模型调用。Token为已知回执用量，未知请求及未计时中断片段另列。",
            "",
            "| 组别 | 采用模型调用 | 本次新增复审调用 | 复用复审调用 | 已知输入token | 已知输出token | 未知usage请求 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for group in "ABCDEF":
        r, cost = rows[group], adopted[group]
        lines.append(
            f"| {group} | {cost['calls']} | {r.get('review_calls_new', 0)} | {r.get('review_calls_reused', 0)} | {cost['input_tokens_known']} | {cost['output_tokens_known']} | {cost['unknown_usage_calls']} |"
        )
    lines.extend(
        [
            "",
            "### 执行耗时与批次规模",
            "",
            "D/E及F前7项目串行，F后半段改为最多两个独立项目同时运行，各项目内部仍按原生产图顺序执行；调度变化已登记到协议和secondary-queue.json，不变更候选池、提示和模型策略。批次4是上限，按相同条件分组后常拆为较小批次；补充取证和结构／证据校验会增加请求。以下耗时为采用阶段操作时间之和，不是端到端GUI延迟，F含6个历史复用阶段。",
            "",
            "| 组别 | 计划候选 | 基础批次 | 平均批次大小 | 模型调用区间秒 | 阶段已知秒 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for group in "DEF":
        p = diagnostics[group]["performance"]
        lines.append(
            f"| {group} | {p['scheduled_candidates']} | {p['scheduled_batches']} | {p['mean_scheduled_batch_size']:.2f} | {p['model_call_seconds_known']:.1f} | {p['stage_seconds_known']:.1f} |"
        )
    lines.extend(["", "## 可追溯产物", ""])
    for title, name in (
        ("冻结协议", "ablation-protocol.md"),
        ("六组成绩与资源总表", "ablation-summary.csv"),
        ("156行逐项目结果", "ablation-per-project.csv"),
        ("676行发现交集", "discovery-overlap.csv"),
        ("逐项目发现交集", "discovery-overlap-per-project.csv"),
        ("逐候选复审去向", "review-transitions.csv"),
        ("2028行金标去向", "review-gold-transitions.csv"),
        ("未决和证据门诊断", "review-diagnostics.json"),
        ("模型、提示和输入池身份", "formal-review-identity.json"),
        ("采用／新增／累计资源", "resources-comparison.json"),
    ):
        lines.append(f"- [{title}]({output / name})")
    text = (
        "\n".join(lines).replace(
            "2028行金标去向（每组676）",
            "2028行金标去向（每组676）",
        )
        + "\n"
    )
    source.write_text(text)
    rows_per = list(csv.DictReader((output / "ablation-per-project.csv").open()))
    if len(rows_per) != 156 or any(
        sum(r["group"] == g for r in rows_per) != 26 for g in "ABCDEF"
    ):
        raise RuntimeError("Six-arm project denominator changed")
    gold_rows = list(csv.DictReader((output / "review-gold-transitions.csv").open()))
    if len(gold_rows) != 2028:
        raise RuntimeError("Review gold transitions do not cover 3 × 676")
    overlap_rows = list(csv.DictReader((output / "discovery-overlap.csv").open()))
    if len(overlap_rows) != 676:
        raise RuntimeError("Discovery overlap denominator changed")
    for group in "DEF":
        cell = data["review_gold_transitions"][group]
        if (
            cell.get("retained", 0) + cell.get("gained_after_review", 0)
            != rows[group]["tp"]
        ):
            raise RuntimeError("Review gold allocations disagree with score")
    save(
        output / "csv-integrity.json",
        {
            "project_rows": 156,
            "overlap_gold_rows": 676,
            "review_gold_rows": 2028,
            "review_allocation_score_equations_verified": True,
        },
    )
    save(
        output / "completion.json",
        {
            "complete": True,
            "groups": 6,
            "projects_per_group": 26,
            "gold": 676,
            "new_review_projects": 72,
            "historical_F_reused": 6,
        },
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    finish(args.base.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
