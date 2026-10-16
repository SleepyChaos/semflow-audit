# IRIS v1 数据集评测准备与阻塞记录

日期：2026-10-13。状态：`blocked_unsupported_language`。已获取材料并完成生产语言门检查，**尚未完成漏洞检测评测**。

## 输入与版本

- 按用户指定的 `git clone --branch v1 --recurse-submodules` 获取仓库，保存在 Git 忽略目录 `.local-workspace/iris-original/`。
- IRIS commit：`67140e84e6a01da2b44803a6208be2ea7bd4bd51`。
- CWE-Bench-Java 子模块 commit：`698fb7248ae30cb7f7782d59c841f05ad70ea9cc`。
- `project_info.csv` SHA-256：`f409c8cd4ff21268bca7a38193b2abb61f6e8914778cfb10bc2e1c56352d78fa`。
- 冻结清单 120 项：CWE-022 55、CWE-078 13、CWE-079 31、CWE-094 21，目标语言均为 Java。
- 克隆包含元数据、补丁、标注与作者结果，**不包含全部目标项目源码或可直接扫描的 CodeQL 数据库**；作者另有源码获取与构建步骤。
- 被测平台为当前工作区，存在用户尚未提交的改动；未修改生产代码，也未调用模型。

## 实测范围与结果

运行入口：`system/scripts/benchmarks/iris_preflight.py`，输出在 Git 忽略目录 `artifacts/iris-v1-20261013/preflight.json`，逐任务保留 `not_evaluated`。

1. 从生产上传函数的实际类型注解读取语言集合，并使用 Pydantic 验证 `java`：得到 `literal_error`，只接受 `python`、`javascript`。这不是 HTTP 请求测试。
2. 调用生产 `extract_snapshot` 对合成纯 Java ZIP 分别选择上述两种语言：两次都返回“压缩包中没有所选语言的源码”。合成探针用于确认语言门，不是漏洞样本或检出能力测试。
3. 生产源码扩展名映射没有 `.java`；默认查询包也只有 Python 与 JavaScript。仅放宽上传参数不足以获得 Java 审计能力。

平台实际评估任务数为 **0**，120 项全部未评估；检出率、precision、F1 均为 `null`。这不能写成 0% 召回率，也不能据此判断平台优于或劣于 IRIS。

## 论文对照

来源：[IRIS ICLR 2025 / arXiv v3](https://arxiv.org/abs/2405.17238)，本地 `research/papers/rules/iris-arxiv-v3.txt`，§5.1、Table 1。论文 CodeQL 版本为 2.15.3，GPT-4 为 `gpt-4-0125-preview`。

| 系统 | 检出数 | 论文检出率 | 平均 FDR | 平均 F1 |
| --- | ---: | ---: | ---: | ---: |
| 论文 CodeQL | 27/120 | 22.50% | 90.03% | 0.076 |
| 论文 IRIS＋GPT-4 | 55/120 | 45.83% | 84.82% | 0.177 |
| 当前平台 | 未评估 | 不可计算 | 不可计算 | 不可计算 |

冻结仓库中 `results/CodeQL.csv` 与 `results/IRIS+GPT-4.csv` 的数值 Recall 行检出总数分别为 27 和 55，与论文总数一致；它们是作者已有结果，**不是本次运行 IRIS 得到的结果**。FDR 使用不完备黄金标注，论文称其为粗略误报上界。

作者 CSV 通常有 121 行，Llama3-70B 有 122 行；不能直接把这些行数作为论文 120 的分母。按 CWE、CVE、作者、仓库、tag 五字段精确匹配，主要 CSV 与本轮清单仅有 100 项匹配。20 项差异包括 `apache/asf`、`CureKit/curekit`、`DSpace 5.10/5.1`、仓库迁移、版本后缀等。部分可能仅为历史别名或格式变化，但必须结合目标 commit 与作者评测实现核对，不能自动当作相同源码版本。预检保存精确匹配子集计数，全清单映射后的分数保持空值。

## 复现与继续条件

从仓库根目录运行：

```sh
PYTHONPATH=system/backend system/.venv/bin/python \
  system/scripts/benchmarks/iris_preflight.py \
  .local-workspace/iris-original artifacts/iris-v1-20261013/preflight.json
```

继续同榜审计需要先补齐平台 Java 支持：上传与语言识别、Java CodeQL 查询包和抽取策略、Java 源码证据解析、粗筛/复核及关联验证。然后获取固定 commit 的目标源码，隔离 evaluator 标注与补丁，核对作者 matcher 与结果映射，冻结模型和预算，从小批真实扫描开始再扩至 120 项。更改系统以支持 Java 属于新增功能，不能把这个改造后的系统冒充本次“当前平台”的结果。

本次未执行第三方构建脚本，未导入修复答案到模型或 RAG，未提交目标源码、模型密钥或审计产物。
