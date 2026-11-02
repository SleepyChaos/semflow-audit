# 脚本导航

从 `system/` 目录运行。实验脚本可能调用真实模型、CodeQL、数据库或 Docker，具体参数及费用边界见对应实验协议。

| 职责 | 入口 |
| --- | --- |
| 初始化与工具准备 | `init_local.py`、`install_query_sources.py`、`install_codeql_lsp.py` |
| 共享内核实验 CLI | `PYTHONPATH=backend .venv/bin/python -m app.cli --help`；[配置与恢复](../../design/experiment-cli.md) |
| 生产知识采集与索引 | `seed_knowledge.py`、`curate_rule_corpus.py`、`expand_rule_corpus.py` |
| 本地链路与真实工具验证 | `verify_live.py`、`benchmarks/run_local.py`、`system/tests/` |
| 三方向正式评测 | `benchmarks/formal_*.py`；[实验断点与协议](../../benchmarks/experiments/README.md) |
| 发现/修复/规则研究 | `benchmarks/discovery_*.py`、`formal_repair*.py`、`rule_*.py`、`rag_*.py` |
| 新样本与浏览器补测 | `benchmarks/supplemental_*.py/mjs`、`chain_*.py/mjs` |
| 历史测试结果归档 | `archive_test_results.py`、`test_archive/`；[版本收据说明](../../benchmarks/testing/README.md) |
| 既有材料盘点 | `benchmarks/current_test_inventory.py`、`inventory_collected_materials.py` |
| 仓库数据打包、验证与恢复 | [archive_research_materials.py](benchmarks/archive_research_materials.py)；[公开数据归档](../../benchmarks/datasets/README.md) |

## 仓库研究数据

```sh
# 校验远程仓库中的压缩包和逐成员 SHA-256
python3 scripts/benchmarks/archive_research_materials.py
# 在新 checkout 中恢复`benchmarks/` 实验输入路径；已有不同内容时拒绝覆盖
python3 scripts/benchmarks/archive_research_materials.py --restore
# 维护归档：从既有本地原件生成发布副本，不执行第三方代码
python3 scripts/benchmarks/archive_research_materials.py --build
```

普通恢复不需要网络或新增依赖。重新打包需要已有原件和 `manifests/local-integrity.json`；不会将论文、答案或测试集自动导入生产 RAG。
