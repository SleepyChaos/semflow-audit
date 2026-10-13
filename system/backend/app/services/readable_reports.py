"""Reader-facing Markdown, with machine records retained in a collapsed appendix."""

import json
import re

from app.services.result_explanations import explain_candidate, explain_validation


def markdown_report(report: dict) -> str:
    audit, summary = report["audit"], report["summary"]
    counts = summary.get("candidate_states", {})
    sections = [
        f"# 审计报告：{audit['project_name']}",
        "## 阅读结论",
        f"静态规则产生 {summary.get('static_alerts', 0)} 条告警；当前分类：已确认 {counts.get('confirmed', 0)} 个，待确认 {counts.get('pending', 0)} 个，证据不足 {counts.get('insufficient', 0)} 个，支持排除 {counts.get('excluded', 0)} 个。",
        "分类来自 AI 复核或人工调整；具体来源以执行及调整记录为准。零告警不代表安全，阶段执行完成也不代表漏洞已修复。",
        f"本次分析的语言：{audit['language']}；源码快照：`{audit['snapshot_hash']}`；CodeQL：{audit['codeql_version']}。",
        "## 问题在哪里、有什么影响",
    ]
    from app.services.ai_report_markdown import narrative_sections

    sections.extend(narrative_sections(report))
    if report.get("ai_report", {}).get("status") != "ready":
        guide = report.get("reader_guide", {})
        candidates = guide.get("candidates")
        if candidates is None:
            candidates = [
                explain_candidate(row, report.get("evidence", []))
                for row in report.get("candidates", [])
            ]
        if not candidates:
            sections.append(
                "本次没有可展示的候选。请检查扫描是否成功、源码覆盖范围，以及是否有未执行的复核。"
            )
        for index, item in enumerate(candidates, 1):
            sections.extend(
                [
                    f"### {index}. {item['title']}",
                    f"位置：`{item['location']}`。判断状态：**{item['status']}**。",
                    f"**为什么值得检查：** {item['observation']}",
                    f"**可能造成什么影响：** {item['risk']}",
                    f"**建议怎么修：** {item['remediation']}",
                    f"**下一步：** {item['next_step']}",
                    item["boundary"],
                ]
            )
    sections.append("## 修复做了什么、验证到哪一步")
    for repair in report.get("repairs", []):
        sections.append(f"### 修复记录 {repair['id'][:8]}")
        for change in repair.get("changes", []):
            sections.append(
                f"修改文件：`{change['file']}`。具体修改见原始记录与 Diff。"
            )
        for check in explain_validation(repair.get("validation", {})):
            sections.append(
                f"- **{check['label']}：{check['status']}**。{check['description']} 下一步：{check['next_step']}"
            )
    if not report.get("repairs"):
        sections.append("尚无修复记录。报告可以先导出，确认缺陷后再生成修复。")
    sections.extend(
        [
            "## 范围与未完成事项",
            "这里只描述本次保存的分析与检查结果；未检查的文件、运行配置和业务路径不属于安全保证。",
            "\n".join("- " + text for text in report.get("limitations", [])),
            "## 原始记录（技术附录）",
            "以下保留模型原文、证据、版本和执行结果，供技术人员复核。",
        ]
    )
    for title, key in [
        ("汇总", "summary"),
        ("覆盖范围", "coverage"),
        ("独立粗筛", "discovery"),
        ("阶段执行", "stages"),
        ("候选与人工判断", "candidates"),
        ("判断历史", "decisions"),
        ("取证证据", "evidence"),
        ("修复与验证", "repairs"),
        ("规则版本", "rules"),
        ("根因关联建议", "root_relations"),
        ("锚点评价", "anchor_assessments"),
    ]:
        value = json.dumps(report.get(key), ensure_ascii=False, indent=2)
        fence = "`" * max(
            3, max((len(m) + 1 for m in re.findall(r"`+", value)), default=3)
        )
        sections.append(
            f"<details>\n<summary>{title}</summary>\n\n{fence}json\n{value}\n{fence}\n\n</details>"
        )
    value = json.dumps(audit.get("findings", []), ensure_ascii=False, indent=2)
    fence = "`" * max(3, max((len(m) + 1 for m in re.findall(r"`+", value)), default=3))
    sections.append(
        f"<details>\n<summary>原始静态告警</summary>\n\n{fence}json\n{value}\n{fence}\n\n</details>"
    )
    return "\n\n".join(sections) + "\n"
