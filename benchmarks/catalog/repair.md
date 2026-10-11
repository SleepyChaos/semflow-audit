# repair 材料清单

核查日期：2026-10-05。已完成一轮检索；上游规模不等于本地可运行规模。

## 数据与复制包

| 材料 | 已收集状态 / 固定版本 | 测什么 | 限制与许可 |
| --- | --- | --- | --- |
| [PatchEval](https://github.com/bytedance/PatchEval) | complete_1000_task_json_framework_scripts_no_images；`ae9b3a7233e9e2fe86dcba8baba24beff9bcbba8` | 真实CVE修复、测试可得性和闭环修复 | 1000=404Python+300JS+296Go；仅176有非空unit_test_cmd；官方230镜像未下载；input.json含fix_func/one-shot泄漏；本固定tree未发现verified数据文件；Apache-2.0 framework; upstream separately licensed；历史：new task metadata; not evaluated |
| [Vul4Py](https://github.com/tabudz/vul4py) | complete_100_task_index_and_harness_no_target_snapshots；`2649d7b89e796738ebc2bc3fa9480dff5ae15898` | Python真实修复/双oracle校准候选 | 100行；evaluate允许functional_rc=999缺失/skip成为plausible，不能全称双测试齐备；未下载全部上游源码/镜像；旧索引已用；no standalone license found; local research only；历史：earlier CSV/pilot used; disjoint repos required |
| [Execution-calibrated patching reproduction](https://zenodo.org/records/21645415) | complete_reproduction_zip；`Zenodo 21645415` | 小型安全+功能oracle、验证器开发 | 复制包8个Python/JS样例已用于旧测试，属于开发；作者SQLite结果不属于本平台；MD5与Zenodo核对；CC-BY-4.0 per Zenodo; upstream as applicable；历史：8 small oracles previously evaluated, development only |
| [BugsInPy](https://github.com/soarsmu/BugsInPy) | complete_framework_bug_metadata_archive；`11c5f1eea954a42132cfd06bf257766a7963e0fd` | 修复业务功能保持与测试环境设计参考 | 固定归档501个bug.info文件，不等于原论文493可重现bugs；普通功能bug非安全漏洞gold；未下载上游项目；no standalone license in fixed archive; local research; upstream licenses separate；历史：not evaluated |
| [EduCollab / Detect-Repair-Verify](https://github.com/Hahappyppy2024/EmpricalVDR) | 188_of_197_selected_source_files_git_blob_verified；`5bb31b561bee09017b1b269839d12c6895f81efa` | 语义业务用例、功能+安全测试、跨修复范围方法 | Py/JS两个项目选取197文本文件，188通过Git blob SHA1核对、9缺失；不是完整快照；排除缓存/数据库/ZIP/图片。完整大包和缺失文件下载失败；生成应用单列，需服务的测试未运行；no root LICENSE found; local research only; no redistribution；历史：not evaluated |
| [VulnRepairEval](https://arxiv.org/abs/2509.03331) | paper_only_public_dataset_unverified；`arxiv v1` | 漏洞利用有效性验证定义 | 23 Python PoC案例仅论文规模；未找到确认的公开完整复制包；需容器/部署，当前仅研究；paper local reading only；历史：not evaluated |
| [RealSec-bench](https://aclanthology.org/2026.findings-acl.1786/) | paper_only；`ACL Findings 2026` | secure-and-correct联合指标参考 | 105任务是安全代码生成、Java，不是当前Python/JS修复主集；paper terms local reading; dataset license unverified；历史：not evaluated |
| [SecRepoBench](https://arxiv.org/abs/2504.21205) | paper_html_only；`arxiv v3` | 仓库上下文和安全completion参考 | 与修复任务不同，C/C++未来扩展，不计当前已支持语言；paper terms local reading；历史：not evaluated |
| [PredicateFix artifact](https://doi.org/10.6084/m9.figshare.26956228) | online_primary_source_verified_local_download_failed；`not locally frozen; do not use mutable main for an experiment` | 静态告警修复与领域知识检索的方法参考 | 论文明确给出Figshare复制包地址，但本轮未获取目录/复制包；桥接谓词帮助找干净范例；告警消失仍需人工正确性确认；不是业务语义双oracle认证集；paper CC-BY-NC-ND-4.0; artifact license not verified；历史：not evaluated |
| [SEC-bench](https://github.com/SEC-bench/SEC-bench) | online_primary_source_verified_local_download_failed；`not locally frozen; do not use mutable main for an experiment` | 隔离环境、安全修复oracle方法参考；未来语言扩展 | NeurIPS 2025主文200已验证实例；C/C++内存安全，sanitizer测试不能取代业务合同；框架/镜像/数据本轮均未下载；不纳入当前Py/JS主表；dataset/framework license not locally verified; upstream licenses separate；历史：not evaluated |

## 论文与专业来源

正式论文、预印本及官方技术报告分别标注；同一工作不同版本不重复计算。

| 文献 | 年份 / 状态 | 价值与核实机构 |
| --- | --- | --- |
| [PatchEval: A New Benchmark for Evaluating LLMs on Patching Real-World Vulnerabilities](https://arxiv.org/abs/2511.11019) | 2025；arXiv preprint | 真实CVE+PoC/单元测试，运行子集需核实；ByteDance official artifact verified; full author affiliations not audited |
| [Vul4Py: Benchmarking Automated Vulnerability Repair in Python with Paired Exploit and Functional Oracles](https://arxiv.org/abs/2608.00692) | 2026；arXiv preprint | 双oracle宣称与脚本实际缺失测试状态分开；not verified |
| [VulnRepairEval: An Exploit-Based Evaluation Framework for Assessing Large Language Model Vulnerability Repair Capabilities](https://arxiv.org/abs/2509.03331) | 2025；arXiv preprint; no formal venue verified | 不能只以语法/复扫判断修复；天津大学 / Singapore Management University / NTU，论文HTML核实 |
| [Detect--Repair--Verify for LLM-Generated Code: A Multi-Language, Multi-Granularity Empirical Study](https://arxiv.org/abs/2603.23633) | 2026；arXiv preprint | 不同上下文与修复范围、业务功能保持；Concordia University, Canada verified in paper |
| [RealSec-bench: A Benchmark for Evaluating Secure Code Generation in Real-World Repositories](https://aclanthology.org/2026.findings-acl.1786/) | 2026；Findings of ACL 2026 | 安全与功能同时满足，生成任务区别修复；not verified |
| [SecRepoBench: Benchmarking Code Agents for Secure Code Completion in Real-World Repositories](https://arxiv.org/abs/2504.21205) | 2025；arXiv preprint version 3 | 真实仓库上下文，completion任务边界；not verified |
| [PredicateFix: Repairing Static Analysis Alerts with Bridging Predicates](https://doi.org/10.1145/3744916.3773159) | 2026；ICSE 2026 | 规则谓词连接缺陷与知识范例；辅助修复资料相关性；北京大学 / 中兴，论文首页核实 |
| [SEC-bench: Automated Benchmarking of LLM Agents on Real-World Software Security Tasks](https://papers.nips.cc/paper_files/paper/2025/file/a9168f1c54e5147027f1e8cf83e1a775-Paper-Conference.pdf) | 2025；NeurIPS 2025 | 可复现环境与sanitizer验证，C/C++未来参考；UIUC / Purdue，正式论文首页核实 |

本地路径及下载状态见同名 JSON；逐文件校验见 `../manifests/local-integrity.json`。所有 raw/论文仅本地保存，未加入 RAG。
