"""Publish completed frozen results; failures stay in every denominator."""

import json
import statistics
from collections import Counter
from pathlib import Path

from app.services.context_materials import save_json

ROOT = Path(__file__).resolve().parents[3]


def group_detail(rows, base):
    result = {}
    for arm, group in base.items():
        selected = [r for r in rows if r["arm"] == arm]
        passed = [r for r in selected if r.get("end_to_end_passed")]
        failures = Counter()
        for row in selected:
            if row.get("end_to_end_passed"):
                continue
            if row.get("oracle", {}).get("status") == "failed":
                failures["hidden_mismatch"] += 1
            elif row.get("error"):
                failures[row["error"]["code"]] += 1
            else:
                failures[row.get("oracle", {}).get("status", "unknown")] += 1
        result[arm] = {
            **group,
            "failure_codes": dict(failures),
            "successful_generation_median_seconds": statistics.median(
                r["generation_seconds"] for r in passed
            )
            if passed
            else None,
            "successful_total_median_seconds": statistics.median(
                r["generation_seconds"] + r.get("evaluation_seconds", 0) for r in passed
            )
            if passed
            else None,
            "successful_unique_query_hashes": len(
                {r["rules"][0]["query_hash"] for r in passed}
            ),
        }
    return result


def main():
    experiments = {}
    for revision, name in [
        ("v7", "rag-stabilization-20261004"),
        ("v8", "rag-stabilization-v8-20261004"),
    ]:
        folder = ROOT / "artifacts/benchmarks" / name
        report = json.loads((folder / "report.json").read_text())
        verified = json.loads((folder / "freeze-verification.json").read_text())
        if not report["complete"] or verified["status"] != "passed":
            raise RuntimeError("Publish only complete verified experiments")
        experiments[revision] = {
            "artifact": str(folder),
            "fresh_requests": 108 if revision == "v7" else 90,
            "reused_controls": 0 if revision == "v7" else 18,
            "groups": group_detail(report["records"], report["groups"]),
            "prompt_hashes": report["manifest"]["prompt_hashes"],
            "corpus_hash": report["manifest"]["new_corpus_hash"],
            "hidden_hash": report["manifest"]["hidden_manifest_hash"],
            "implementation_hashes": report["manifest"]["implementation_hashes"],
            "freeze_verification": verified,
        }
    source = json.loads(
        (
            ROOT / "artifacts/benchmarks/v8-external-source-20261004/report.json"
        ).read_text()
    )
    extra = json.loads(
        (
            ROOT
            / "artifacts/benchmarks/v8-source-extension-additional-20261004/report.json"
        ).read_text()
    )
    coverage = json.loads(
        (ROOT / "artifacts/research/corpus-coverage-v4.json").read_text()
    )
    summary = {
        "date": "2026-10-04",
        "experiments": experiments,
        "source_extension": {
            "requests": len(source["rows"]),
            "compiled": sum(r["compiled"] for r in source["rows"]),
            "development_passed": sum(
                r.get("development", {}).get("status") == "passed"
                for r in source["rows"]
            ),
            "project_replay_statuses": dict(
                Counter(
                    r.get("project_replay", {}).get("status") for r in source["rows"]
                )
            ),
            "holdout_passed": sum(
                r["independent"]["status"] == "passed" for r in source["rows"]
            ),
            "additional_passed": sum(
                r["result"]["status"] == "passed" for r in extra["records"]
            ),
            "unique_rule_hashes": len({r["query_hash"] for r in extra["records"]}),
            "seconds": [r["seconds"] for r in source["rows"]],
            "budget_rule_tokens": source["policy"]["rule_tokens"],
        },
        "corpus": json.loads(
            (ROOT / "artifacts/materials/rag-corpus-v4/manifest.json").read_text()
        )["summary"],
        "availability_checks": {
            "checks": coverage["checks"],
            "statuses": coverage["statuses"],
        },
        "limitations": [
            "Six task families repeated three times, not eighteen independent vulnerabilities",
            "Old v8 controls are referenced, not regenerated",
            "FP/TP/FN conditioned on executed generated rules; failures remain in end-to-end denominator",
            "Hand-authored external API cases are not a public benchmark and repeated rules may have identical hashes",
            "Embedding costs are excluded from chat usage, included in generation wall time",
            "Local caches, interleaving and supplementary tests limit speed inference",
        ],
    }
    save_json(ROOT / "benchmarks/reports/rag-stabilization-summary.json", summary)
    first = experiments["v7"]["groups"]
    second = experiments["v8"]["groups"]

    def table(groups):
        lines = [
            "| 组别 | 请求 | 编译 | 开发执行 | 生成可评估规则 | 端到端通过 | 成功请求生成中位秒 | 成功请求含隐藏评估中位秒 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for arm, g in groups.items():

            def f(value):
                return f"{value:.2f}" if value is not None else "未成功"

            lines.append(
                f"| {arm} | {g['requests']} | {g['observed_compile_passed']} | {g['development_passed']} | {g['generated']} | **{g['end_to_end_passed']}/{g['requests']}** | {f(g['successful_generation_median_seconds'])} | {f(g['successful_total_median_seconds'])} |"
            )
        return "\n".join(lines)

    text = (
        """# RAG 规则稳定化阶段结果

日期：2026-10-04。完整数据见 [汇总 JSON](rag-stabilization-summary.json)，输入、预算、消融与隔离见 [协议](rag-stabilization-protocol.md)。旧历史报告与本轮全部失败保留。

## 已完成的改动

1. 模型输入保留完整源码、漏洞描述和两库正文；把大体积官方验证元数据移到不可变材料引用。重复读返回已有证据与观察，最多两次纠正，仍停滞则停止；恢复不重复模型/工具执行。
2. 区分源码准备与规则生成：前者只解释实际源/传播/汇点和必要信任依据，提供真实 EOF/窗口完整性及观察到的基线；不把下一阶段知识缺失或未经执行的业务契约当成自动阻断条件。至少一条源码事实引用、critical unknown 阻断、自定义 API 信任文档要求仍保留。
3. 默认支持 Python/JavaScript eval、SQL、反射 XSS 的类型化规格＋固定官方流分析模板。有限 Python eval 外部调用返回值 source 扩展需实际导入/调用与不可信返回文档，通过真实声明校验；其余用途/策略仍是实验性自由 QL 草稿。官方模板复用不是新增检测能力。
4. 重试视图保留完整上一候选、所有匹配诊断及邻近行、正反例实际/预期位置与状态，移除重复 SARIF 路径与依赖安装日志；不截断代码。预算按实际模型 JSON，完整 pretty 产物保留。不同 source 模型绑定不同规则 ID。
5. 编译→开发正反例→原项目单规则→样例批准→独立验收→发布门保留；补漏和业务确认分开，不自动发布、不自动确认。修复模块行为不在本轮改动范围。

## 第一轮：v7 与四组件消融

108 个新生成请求。同集/模型/6000 输出预算、完整负结果：

"""
        + table(first)
        + """

full v7 12/18 未达标。关闭精简降到5/18，自由QL8/18，说明在本次任务上上下文体积和生成空间是主要工程问题。关闭进度反馈与仅BM25均15/18，不能宣称进度反馈或向量提升了准确率；重复读取行为的确定性回归测试仅证明循环处理正确。

开发阶段日志显示：源码取证要求尚未提供的API/完整业务知识，完整短文件被误认为还有未读后文；自由QL重试被验证元数据和pretty JSON推过上下文门槛。第二轮修改基于这些开发观察，未修改隐藏源码/标签或按隐藏案例增加框架特判。

## 第二轮：v8 和阶段/检索消融

90 个新生成请求；全部18个旧K对照明确引用第一轮，不重复计数。同一冻结模型和预算：

"""
        + table(second)
        + """

移除范围提示仍保留v8阶段合同与源码引用门；提前RAG在inspect前取回同一知识并注入精简全文；BM25只改变检索方法，Python ApiGraphs声明槽各组均固定词法取回；自由QL关闭类型化约束，执行门相同。第一轮→第二轮同时改变阶段合同、范围材料和重试装配，因此不是单一提示词因果实验。

下表包含全部请求的调用与token，不以失败请求较短耗时冒充加速；embedding不计入chat数量和token，生成壁钟包含检索。旧K与第二轮时序不同时，首批额外SDK测试存在本机并发资源竞争，缓存也影响耗时。

| v8组别 | Chat调用 | 输入token | 输出token | 未通过代码/阶段计数 |
|---|---:|---:|---:|---|
"""
    )
    for arm, g in second.items():
        text += f"| {arm} | {g['model_calls']} | {g['input_tokens']} | {g['output_tokens']} | {json.dumps(g['failure_codes'], ensure_ascii=False)} |\n"
    g = second["full_v8"]
    text += f"""
完整 v8 隐藏执行 {g["hidden_executed"]}/18，执行条件 TP={g["conditional_tp"]}、FP={g["conditional_fp"]}、FN={g["conditional_fn"]}。未生成请求不能视作无漏洞，总体工程指标为端到端 {g["end_to_end_passed"]}/18。六类任务每类三轮，不能外推为总体漏洞准确率或统计显著效果。

## 自定义 source 与新正反例

三轮外部事件 API 测试：编译、开发正反例、原项目复跑命中目标候选（待人工根因确认）、独立变体均3/3。额外别名导入/辅助函数传播两个正例，以及数值净化、常量eval、可信另一个API、局部模块遮蔽四个反例，三条已生成规则均通过。该数据手写、仅评估器持有，不传回模型或知识库；三轮只有 {summary["source_extension"]["unique_rule_hashes"]} 个独立query hash，不能称三种新检测器或标准基准成绩。

SDK使用产品当时8000输出预算，与旧集6000分列。总耗时 {", ".join(f"{s:.2f}" for s in summary["source_extension"]["seconds"])} 秒，包含生成和独立测试，不能与旧集单独生成耗时混比。

## 知识库质量

271个参考原文来源、141个完整查询，130个官方开发测试通过、8个仅编译通过、3个失败排除；真实2048维embedding索引覆盖全部参考和138个合格范例。40项双集合材料可用性检查全部通过。详见 [扩库报告](rag-corpus-expansion-results.md)。可用性、编译、官方开发测试和新任务准确率分别统计。

## 能支持的结论和后续方向

- 若完整v8恢复至少15/18，可称恢复旧强方案的工程稳定性；它还包含实际源码准备与有限自定义source，不等于超越原生CodeQL检测能力或证明RAG独立增益。
- 向量与提前RAG是否有优势以本轮表格为准；没有稳定优势时不增加默认调用和上下文。无reranker，保留BM25作为可控对照/降级选择。
- 固定Python库对隐藏XSS变体的覆盖缺口仍需下一阶段一般性框架建模与独立版本测试；本轮不按隐藏数据特判。自由QL不承诺稳定生成任意漏洞家族。
- 下一阶段优先补不同框架/真实未建模API的新任务与安全反例，扩展可验证source/sink/屏障规格；增补30个版本化指南、20个真实编译修正案例，保持独立评估不入库。
- 速度优化应在质量门保留的条件下测数据库/查询编译复用、取证共享与定向上下文；不能以关闭执行检查或失败提前退出算提速。

没有执行GUI测试、被审计服务启动或漏洞利用复测。普通代码/真实CLI与部署版本的最终校验另见验收补充。
"""
    (ROOT / "benchmarks/reports/rag-stabilization-results.md").write_text(text)
    print(
        json.dumps(
            {
                k: {a: g["end_to_end_passed"] for a, g in v["groups"].items()}
                for k, v in experiments.items()
            }
        )
    )


if __name__ == "__main__":
    main()
