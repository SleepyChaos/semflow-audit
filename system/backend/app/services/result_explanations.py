"""Chinese reader guidance derived from saved facts, without new verdicts or calls."""

import re

HUMAN_STATUS = {
    "confirmed": "已人工确认",
    "pending": "待人工确认",
    "excluded": "人工判断支持排除",
    "insufficient": "证据不足，暂不能判断",
}
WEAKNESSES = {
    "CWE-79": (
        "网页输出未正确转义（XSS）",
        "如果不可信输入被当作网页代码处理，攻击者可能让访问者的浏览器执行脚本。",
        "根据输出位置正确转义；HTML 文本、属性和脚本位置需要不同的处理方式。",
    ),
    "CWE-89": (
        "数据库查询注入（SQL 注入）",
        "如果用户输入改变数据库查询的结构，攻击者可能读取或修改超出权限的数据。",
        "使用参数化查询，把数据和 SQL 指令分开，并保留权限检查。",
    ),
    "CWE-78": (
        "系统命令注入",
        "如果用户输入进入系统命令，攻击者可能让服务器执行额外指令。",
        "优先避免 shell 拼接，使用固定程序与独立参数，并约束允许的操作。",
    ),
    "CWE-94": (
        "不可信输入被当作代码执行",
        "如果输入被当作程序执行，攻击者可能控制服务器上的代码行为。",
        "用满足业务需求的解析器替代动态执行，限制允许的数据和操作。",
    ),
    "CWE-22": (
        "文件路径越界（路径穿越）",
        "如果输入能跳出允许目录，攻击者可能访问本不应开放的文件。",
        "规范化路径并核对最终位置确实在允许目录内。",
    ),
}


def explain_candidate(candidate: dict, evidence: list[dict]) -> dict:
    weakness = candidate.get("weakness", "unknown")
    title, risk, remediation = WEAKNESSES.get(
        weakness,
        (
            "待核实的安全问题",
            "尚不能从现有分类确定具体影响，请核对原始分析与源码证据。",
            "先确认实际输入、敏感操作及已有防护，再确定修复方式。",
        ),
    )
    location = candidate.get("location") or {}
    file, line = location.get("file"), location.get("line")
    position = f"{file}:{line}" if file and line else file or "位置待核实"
    quote = ""
    if file and isinstance(line, int):
        for item in evidence:
            ref = item.get("reference") or {}
            if (
                item.get("id") not in candidate.get("evidence_ids", [])
                or item.get("kind") != "code"
                or ref.get("file") != file
            ):
                continue
            start = ref.get("start_line", 1)
            lines = item.get("content", "").splitlines()
            if isinstance(start, int) and 0 <= line - start < len(lines):
                quote = lines[line - start].strip()[:300]
                break
    description = candidate.get("description", "")
    observation = (
        description
        if re.search(r"[\u4e00-\u9fff]", description)
        else "候选分析指出这里可能存在安全条件缺口；具体依据请核对关联源码和原始模型说明。"
    )
    if weakness == "CWE-79" and re.fullmatch(
        r"return\s+request\.args\[[^\n]+\]", quote
    ):
        observation = "关联源码这一行直接返回 URL 查询参数。如果返回内容按 HTML 处理，输入中的标签可能被浏览器当作网页代码，而不是普通文字。还需结合响应类型和上下游防护核对。"
    state = candidate.get("status", "pending")
    next_step = {
        "confirmed": "已有人工作出确认，可选择此缺陷生成修复；修复后还需要功能与漏洞测试。",
        "excluded": "查看人工判断理由和反证；如出现新证据，可以重新记录判断。",
        "insufficient": "补充缺失的源码、配置或测试证据，再进行复核。",
    }.get(
        state,
        "先核对关联证据，再填写判断理由并确认或排除；AI 建议不会自动成为已确认漏洞。",
    )
    return {
        "candidate_id": candidate.get("id"),
        "title": title,
        "location": position,
        "status": HUMAN_STATUS.get(state, "状态待核实"),
        "observation": observation,
        "source_quote": quote,
        "risk": risk,
        "remediation": remediation,
        "next_step": next_step,
        "boundary": "风险和修复方向是类型导读；实际结论以源码、人工判断与执行证据为准。",
    }


def explain_validation(validation: dict, comparison: dict | None = None) -> list[dict]:
    rows = []
    environment = validation.get("environment") or {}
    if environment:
        rows.append(
            {
                "label": "验证环境",
                "status": "环境未就绪"
                if environment.get("status") == "blocked"
                else "需检查",
                "description": str(
                    environment.get("output")
                    or environment.get("reason")
                    or "验证环境没有提供有效结果。"
                ),
                "next_step": "准备配置的验证镜像，确认 Docker 可用后创建新的修复验证记录；本次受阻不证明补丁错误。",
            }
        )
    tests = validation.get("isolated_tests") or {}
    profile, state = tests.get("profile"), tests.get("status")
    syntax = profile == "syntax"
    label = "语法检查" if syntax else "项目测试"
    if tests:
        status = {
            "passed": "通过",
            "failed": "未通过",
            "needs_review": "检查不完整，需复核",
            "not_run": "未执行",
        }.get(state, "状态待核实")
        if state == "passed":
            description = (
                "语法检查通过，只说明代码可以被解析，不证明业务正常或漏洞被阻断。"
                if syntax
                else "配置的项目测试通过；只有测试明确断言的行为得到了验证，未测路径仍未知。"
            )
        else:
            description = (
                "检查没有提供完整通过结果，请展开技术详情核对输出、依赖或未验证文件。"
            )
        rows.append(
            {
                "label": label,
                "status": status,
                "description": description,
                "next_step": "补充正常业务和攻击输入测试；缺少依赖时先准备项目验证镜像。",
            }
        )
    if syntax or not tests:
        rows.append(
            {
                "label": "功能测试",
                "status": "未执行",
                "description": "本条记录没有执行项目功能测试，不能判断原有业务是否保持正常。",
                "next_step": "准备项目依赖和独立测试，在表单选择 pytest 或 Node.js 项目测试。",
            }
        )
    rows.append(
        {
            "label": "漏洞验证",
            "status": "未执行",
            "description": "本条记录没有单独记录修复前后的攻击验证；项目测试是否覆盖安全条件，需审阅测试内容。",
            "next_step": "用相同攻击输入比较修复前后，同时检查正常输入；记录预期、实际结果和对应快照。",
        }
    )
    rescan = validation.get("rescan") or {}
    status = {
        "passed": "规则检查通过",
        "failed": "未通过",
        "needs_review": "需复核",
        "not_run": "未执行",
    }.get(rescan.get("status"), "无结果")
    rows.append(
        {
            "label": "CodeQL 复扫",
            "status": status,
            "description": "复扫只检查所选规则是否仍报警；原规则未发现的 AI 候选，不能靠零告警证明修好。"
            if rescan.get("status") != "not_run"
            else "本次未执行静态复扫。",
            "next_step": "需要时启用复扫，并与独立漏洞测试一起判断。",
        }
    )
    if validation.get("semantic_scope"):
        rows.append(
            {
                "label": "修复语义说明",
                "status": "已记录说明",
                "description": "保存了修复目标和业务理解；这是一份说明，不是执行过的功能或漏洞测试。",
                "next_step": "核对改动范围与业务预期。",
            }
        )
    if comparison and comparison.get("status") != "missing":
        status = {
            "passed": "测试范围内通过",
            "failed": "未通过",
            "inconclusive": "证据不足",
            "stale": "材料已变化，需重新验证",
            "queued": "排队中",
            "running": "正在执行",
        }.get(comparison.get("status"), "执行受阻")
        for row in rows:
            if row["label"] == "漏洞验证":
                row.update(
                    status=status,
                    description=comparison.get(
                        "summary", "同一组测试的前后比较尚未完成"
                    ),
                    next_step="查看下方逐项前后对比，审阅测试断言、业务预期和补丁后再决定接受。",
                )
            if row["label"] == "功能测试" and comparison.get("status") == "passed":
                row.update(
                    status="已列用例前后均通过",
                    description="前后对比已执行所列正常功能测试；没有覆盖的业务路径仍未知。",
                    next_step="核对测试是否覆盖你需要保留的功能。",
                )
    return rows
