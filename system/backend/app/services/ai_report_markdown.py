"""Render AI prose alongside authoritative host status and source locations."""

from app.services.result_explanations import HUMAN_STATUS


def narrative_sections(report: dict) -> list[str]:
    generated = report.get("ai_report", {})
    if generated.get("status") != "ready":
        return [
            "## AI 中文报告尚未生成",
            "下面是系统根据保存记录整理的基础信息，不是 AI 撰写的项目分析。请先生成 AI 中文报告。",
        ]
    narrative = generated["narrative"]
    candidates = {row["id"]: row for row in report["candidates"]}
    sections = [
        "## AI 中文分析",
        narrative["overview"],
        "以下文字由 AI 根据本任务的源码证据和保存记录生成；人工状态与验证结果以原始记录为准。",
    ]
    for index, issue in enumerate(narrative["issues"], 1):
        row = candidates[issue["candidate_id"]]
        location = row.get("location") or {}
        position = location.get("file", "位置待核实")
        if location.get("line"):
            position += f":{location['line']}"
        sections.extend(
            [
                f"### {index}. {issue['title']}",
                f"位置：`{position}`；人工状态：**{HUMAN_STATUS.get(row['status'], row['status'])}**。",
                f"**这里发生了什么：** {issue['explanation']}",
                f"**可能造成什么影响：** {issue['impact']}",
                "**AI 修复建议：**\n\n"
                + "\n".join("- " + text for text in issue["fix_suggestions"]),
                "**建议如何验证：**\n\n"
                + "\n".join("- " + text for text in issue["verification_suggestions"]),
                "关联证据："
                + ", ".join(f"`{identifier}`" for identifier in issue["evidence_ids"]),
            ]
        )
    sections.extend(
        [
            "## AI 对修复和验证的解释",
            narrative["repair_review"],
            "## 尚未确定的事项",
            "\n".join("- " + text for text in narrative["limitations"]),
            "## 建议的下一步",
            "\n".join("- " + text for text in narrative["next_steps"]),
        ]
    )
    return sections
