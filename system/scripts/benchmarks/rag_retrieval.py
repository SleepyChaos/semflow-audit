"""Small original held-out-question BM25 smoke benchmark; not rule-generation accuracy."""

import json
import statistics
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "system/backend"))
from sqlmodel import Session, delete
from app.core.db import engine
from app.models import User
from app.persistence.knowledge_models import KnowledgeChunk
from app.adapters.retrieval.knowledge import import_knowledge, KnowledgeRetriever

MATERIAL = [
    (
        "py-eval",
        "python",
        "Python eval 动态执行审计。CodeQL 调用表达式 Call.getFunc 可定位名为 eval 的危险函数。单纯匹配 sink 不能证明污点路径。需要受控输入 source 到 sink 的可达数据流。",
        "python 如何追踪用户输入进入动态求值函数 eval",
    ),
    (
        "py-sql",
        "python",
        "Python SQL 注入 SQL injection。sqlite3 execute 应使用占位符 ? 和单独参数元组。将 request.args 拼接进 SELECT 查询字符串会使数据变为语句结构。CWE-089。",
        "python sqlite3 拼接查询 SQL 注入怎样给出安全负例",
    ),
    (
        "py-shell",
        "python",
        "Python 命令注入 subprocess shell=True 或 os.system 接收外部参数。shell=False 参数列表减少 shell 元字符解释。CWE-078 command injection。需要检查允许执行程序和参数边界。",
        "python subprocess shell=True 命令注入 CWE-078",
    ),
    (
        "py-ql",
        "python",
        "CodeQL Python 自定义规则依赖 codeql/python-all。qlpack.yml 与 codeql-pack.lock.yml 固定依赖版本。query compile --check-only 校验类型语法，并使用 --additional-packs 提供锁定库。",
        "python CodeQL 规则编译依赖锁文件 additional-packs",
    ),
    (
        "js-eval",
        "javascript",
        "JavaScript Express req.query 外部输入进入 eval 是代码注入风险。CodeQL JavaScript 数据流模型识别 Express source。CWE-094。Number 转换不是通用 eval 功能等价修复。",
        "javascript Express req.query 到 eval 污点审计",
    ),
    (
        "js-sql",
        "javascript",
        "JavaScript mysql query 接收拼接的 SELECT 字符串存在 SQL injection。参数化 query(sql, values, callback) 的占位符绑定避免数据影响语句。CWE-089。",
        "javascript mysql SQL 注入 参数化 query 负例",
    ),
    (
        "js-shell",
        "javascript",
        "JavaScript child_process.exec 使用 shell 解释完整命令字符串。外部 req.query 拼接造成 command injection。execFile 使用固定程序和参数数组仍需要参数安全约束。CWE-078。",
        "javascript child_process.exec 外部参数命令注入",
    ),
    (
        "js-ql",
        "javascript",
        "CodeQL JavaScript 规则依赖 codeql/javascript-all；TypeScript 共用抽取器，但补丁运行验证必须使用项目编译配置。生成规则需可解析的正例和负例，以及精确期望位置。",
        "javascript CodeQL TypeScript 规则正例负例验证",
    ),
]


def main():
    user = uuid4()
    with Session(engine) as session:
        session.add(
            User(
                id=user,
                email=f"{user}@benchmark.invalid",
                hashed_password="not-a-login",
            )
        )
        session.commit()
    directory = ROOT / "artifacts/benchmarks" / ("rag-" + str(user))
    directory.mkdir(parents=True)
    report = {
        "dataset": "original retrieval micro-benchmark v1, 8 documents and 8 independently phrased queries; not standard data",
        "retrieval": "actual Haystack BM25 with persisted PostgreSQL chunks; shared seed documents remain eligible",
        "embedding": "not configured; vector quality not measured",
        "rule_generation": "not measured without real model",
        "rounds": [],
    }
    try:
        versions = {}
        for name, language, content, _ in MATERIAL:
            versions[name] = import_knowledge(
                user, name, "original-benchmark:" + name, language, content
            )["version"]
        for index in range(3):
            cases = []
            for name, language, _, question in MATERIAL:
                start = time.perf_counter()
                results = KnowledgeRetriever().retrieve(
                    user, language, question, top_k=3
                )
                rank = next(
                    (
                        position + 1
                        for position, row in enumerate(results)
                        if row["version"] == versions[name]
                    ),
                    None,
                )
                cases.append(
                    {
                        "expected": name,
                        "query": question,
                        "rank": rank,
                        "seconds": time.perf_counter() - start,
                        "citations_valid": all(
                            row["digest"] and row["version"] and row["source"]
                            for row in results
                        ),
                        "retrieved": [
                            {
                                "title": row["title"],
                                "version": row["version"],
                                "methods": row["methods"],
                            }
                            for row in results
                        ],
                    }
                )
            report["rounds"].append(
                {
                    "round": index + 1,
                    "recall_at_3": sum(row["rank"] is not None for row in cases)
                    / len(cases),
                    "mrr_at_3": sum(
                        1 / row["rank"] if row["rank"] else 0 for row in cases
                    )
                    / len(cases),
                    "median_seconds": statistics.median(
                        row["seconds"] for row in cases
                    ),
                    "cases": cases,
                }
            )
        (directory / "dataset.json").write_text(
            json.dumps(MATERIAL, ensure_ascii=False, indent=2)
        )
        (directory / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2)
        )
        print(
            json.dumps(
                {
                    "report": str(directory / "report.json"),
                    "rounds": [
                        {k: v for k, v in row.items() if k != "cases"}
                        for row in report["rounds"]
                    ],
                },
                ensure_ascii=False,
            )
        )
    finally:
        with Session(engine) as session:
            session.exec(delete(KnowledgeChunk).where(KnowledgeChunk.owner_id == user))
            session.exec(delete(User).where(User.id == user))
            session.commit()


if __name__ == "__main__":
    main()
