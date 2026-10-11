"""Group tests by documented product improvements while preserving comparison arms."""

import json
from collections import Counter


def classify(rows, definitions):
    groups = definitions["improvements"]
    for row in rows:
        path = row["path"]
        candidates = []
        for group in groups:
            score = 10000 if path in group.get("reports", []) else 0
            for prefix in group.get("path_prefixes", []):
                if path.startswith(prefix):
                    score = max(score, len(prefix))
            if score:
                candidates.append((score, group["id"]))
        if candidates:
            highest = max(score for score, _ in candidates)
            winners = {name for score, name in candidates if score == highest}
            if len(winners) != 1:
                raise ValueError("Ambiguous improvement ownership: " + path)
            row["improvement_archive_group"] = winners.pop()
            row["grouping_basis"] = "explicit_documented_series_or_run_path"
        else:
            row["improvement_archive_group"] = "UNMAPPED"
            row["grouping_basis"] = "not_inferred_from_date_or_current_version"
    return groups


def render_group_index(archive_id, groups, rows):
    counts = Counter(row["improvement_archive_group"] for row in rows)
    lines = [
        "# 按项目改进版本归档",
        "",
        f"归档批次：`{archive_id}`。",
        "",
        "IMPROVE 编号是本次按项目功能改进边界新增的内部归档名称，不是既有 Git tag 或全项目发行版本。",
        "VALIDATION 编号表示既有实现的新样本补充验证，不声明新增产品改进版本。",
        "每组包含该轮改进的验证与旧版对照；组归属不把所有对照臂改标成新版。",
        "跨版本测试以原组别/Prompt/配置/源码收据为准；无法归属的结果单列，不按日期猜测。",
        "",
        "| 改进归档版本 | 功能边界 | 状态 | 结果文件数 |",
        "| --- | --- | --- | ---: |",
    ]
    for group in groups:
        lines.append(
            f"| [{group['id']}](improvements/{group['id']}.md) | {group['name']} | "
            f"{group['status']} | {counts[group['id']]} |"
        )
    lines.append(
        f"| [UNMAPPED](improvements/UNMAPPED.md) | 版本归属未核实 | 待追溯 | {counts['UNMAPPED']} |"
    )
    return "\n".join(lines) + "\n"


def render_group(archive_id, group, rows):
    selected = [row for row in rows if row["improvement_archive_group"] == group["id"]]
    lines = [
        f"# {group['id']}：{group['name']}",
        "",
        f"归档批次：`{archive_id}`。状态：{group['status']}。",
        "",
        "## 项目改进边界",
        "",
        group["change"],
        "",
        "## 版本与对照",
        "",
        group["version_scope"],
        "",
        "## 结果使用口径",
        "",
        group["result_scope"],
        "",
        "该组是测试归档归属；VALIDATION 组只补充验证既有实现。旧版对照臂仍绑定其原版本，实际实现身份逐条查看同批配置和哈希收据。",
        "[共享的归档时环境](../environment.json)只适用于当前源码快照；不能补填历史环境。",
        "",
        "## 报告与机器汇总",
        "",
        "| 结果 ID | 文件 | 相关内容版本收据 |",
        "| --- | --- | --- |",
    ]
    for row in selected:
        if row["role"] == "report":
            lines.append(
                f"| `{row['result_id']}` | [{row['path']}](../../../../{row['path']}) | "
                f"{', '.join(row['test_version_ids']) or '仅声明或缺历史冻结，见登记册'} |"
            )
    lines += [
        "",
        "## 原始结果与配置收据",
        "",
        "完整 SHA-256、原字段及引用在[登记册](../registry.json)；原件与忽略目录中的冻结副本各保存一份。",
        "",
        "| 结果 ID | 原文件 | SHA-256（前12位） | 同批配置/版本收据 ID |",
        "| --- | --- | --- | --- |",
    ]
    for row in selected:
        if row["role"] == "local_receipt":
            lines.append(
                f"| `{row['result_id']}` | `{row['path']}` | `{row['sha256'][:12]}` | "
                f"{', '.join(row['version_receipt_ids']) or '缺失，沿用原文件声明'} |"
            )
    return "\n".join(lines) + "\n"


def write_group_archives(public, local, archive_id, definitions, rows):
    groups = classify(rows, definitions)
    (public / "improvements").mkdir()
    (local / "by-improvement").mkdir()
    (public / "improvement-index.md").write_text(
        render_group_index(archive_id, groups, rows)
    )
    fallback = {
        "id": "UNMAPPED",
        "name": "历史归属待核实",
        "status": "unresolved",
        "change": "这些收据尚无足够证据归到明确的项目改进版本。",
        "version_scope": "不继承当前默认版本，不通过文件修改时间推断测试版本。",
        "result_scope": "保留原结果与哈希；只供追溯，不能作为某个改进版本已通过的证明。",
    }
    for group in [*groups, fallback]:
        (public / "improvements" / (group["id"] + ".md")).write_text(
            render_group(archive_id, group, rows)
        )
        selected = [
            row for row in rows if row["improvement_archive_group"] == group["id"]
        ]
        manifest = {
            "archive_id": archive_id,
            "improvement_archive_group": group["id"],
            "source_receipts": [
                {
                    "result_id": r["result_id"],
                    "sha256": r["sha256"],
                    "copy_path": "receipts/" + r["path"],
                }
                for r in selected
            ],
        }
        (local / "by-improvement" / (group["id"] + ".json")).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        )
    return groups
