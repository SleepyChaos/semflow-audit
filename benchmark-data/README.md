# 三条创新链路的正式评测材料

材料收集起始：2026-10-05；组织更新：2026-10-08。此目录与生产 RAG 知识库分开，保存公开基准、论文、固定版本源码、来源和评测协议。后续已完成OWASP48冻结验收；最新测试分类与统计见下方入口，原收集快照保留。

## 快速入口

- [两类测试总入口](test-programs/README.md)：A类通用基准、B类专项同任务比较。
- [当前材料与竞品统计](test-programs/inventory.md)：32项材料候选、10个主要对照及实际运行状态。
- [当前文献登记](catalog/current-papers.md)：43项去重登记，25个PDF文件对应21项文献。
- [ABSENTIA专项方案](test-programs/specialized-comparisons/absentia.md)：BAC-Bench同任务输入、配对评分和复现条件。
- [OWASP48最新冻结结果](experiments/owasp48-final-comparison.md)：平台与CodeQL、Bandit、阿里OCR的实际比较及限制。
- [正式实验计划与断点续接入口](experiments/README.md)：首批项目、对照流程、任务状态和下一步。
- [首轮实际测试结果及论文对比条件](experiments/calibration-results.md)：校准批次完成，正式同榜提升尚未证明。
- [三个方向首轮检索结果与未找到的部分](search-round-report.md)
- [漏洞发现与复审材料](catalog/discovery.md)：OWASP Python、RealVuln、VulnGym、SastBench、CrossCommit、OpenSSF、SecBench.js 等。
- [QL 规则生成材料](catalog/rules.md)：QLCoder、IRIS、CQLLM、真实项目规则候选与检索评价参考。
- [代码修复材料](catalog/repair.md)：PatchEval、Vul4Py、双 oracle 复制包、BugsInPy、EduCollab 等。
- [评测协议与推进顺序](evaluation-protocol.md)：输入边界、评分、消融、速度与复现条件。
- [材料清单](manifests/collection-summary.json)：本地核对数量、收集状态、失败和未完成项。
- `manifests/local-integrity.json`：逐文件 SHA256、大小、格式校验和归档来源关联；仅本地保存。

## 三方向材料用途（初始收集方案）

| 创新链路 | 第一批材料 | 为什么选它 | 还要准备什么 |
| --- | --- | --- | --- |
| 双引擎发现 | OWASP Python + 6 个真实 JS 配对项目 | 前者含明确正负例；后者含完整项目上下文与修复前后版本 | 清除答案提示、确认目标根因和负例、冻结 CodeQL 基线 |
| Agent 取证与复审 | VulnGym 人工确认子集 + SastBench | 分别检查入口到危险操作的证据，以及既有告警真假判断 | 下载目标仓库并按语言筛选；仅评测器可见 trace/ground truth |
| RAG 规则生成 | 独立真实 Py/JS 目标 + OWASP 同 CWE 安全对例 | 能测编译之外的实际定位、漏检增益和外推误报 | 自建并审核隐藏任务；QLCoder/IRIS 的 Java/C 主集只能作方法参考 |
| 语义辅助修复 | PatchEval Py/JS + 校准后的 Vul4Py | 真实漏洞和修复资料，适配当前语言 | 筛出实际具备安全与业务测试的条目；缺失测试不能计成功 |

实际核对：OWASP Python 1,230 个用例（452 正、778 负、14 类）；PatchEval 1,000 条任务（Python 404、JS 300、Go 296），其中仅 176 条填写非空 `unit_test_cmd`；Vul4Py 100 条索引；VulnGym 408 条入口标注，其中 393 条人工确认；新 JS 配对项目 6/6 已有双快照。上述数量的单位不同，不能相加称为“已可运行样本”。

## 目录与保密边界

```text
benchmark-data/
  catalog/          # 可版本管理的文献/数据用途、来源、许可及限制
  test-programs/    # 通用/专项计划、当前统计；不移动既有原始材料
  manifests/        # 公共汇总 + 本地逐文件完整性记录
  raw/              # 第三方原始材料，含答案，仅本地保存
  papers/           # PDF/HTML 原文，仅本地阅读，不随仓库发布
  evaluator-only/   # 评测器答案、固定选样清单、修复提交
  model-inputs/     # 未来经审核后的模型输入，目前未准备
```

`raw` 不是可直接上传目录：它包含标签、修复版本、作者规则和 PoC。只有建立字段白名单与源码去标签后，才能从中导出 `model-inputs`。没有向 RAG 导入本轮测试材料。

旧 18 次规则实验、旧 20 项真实项目 pilot、8 个已测小 oracle，以及当前 141 个 RAG 官方范例仍属于开发材料。新 6 项候选已排除旧 pilot 的仓库，但完整历史暴露审计尚未完成，暂不称为完全未见的正式测试集。

## 可复现检查

在仓库根目录运行：

```sh
python3 scripts/benchmarks/inventory_collected_materials.py
```

该脚本只读取文件和归档，生成清单，不导入或执行第三方源码。固定版本和来源见各方向 JSON；新配对快照的 12 个提交与下载地址见 `raw/project-pairs/manifest.json`。下载失败或超过收集大小限制的部分保留在完整性清单中，不计作有效材料。

本轮未进行 GUI 测试、启动目标服务、安装基准依赖或运行漏洞利用。涉及容器与服务的复制包先作研究材料，后续仍按已经确认的评测边界筛选。
