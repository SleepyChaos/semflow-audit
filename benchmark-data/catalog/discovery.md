# discovery 材料清单

核查日期：2026-10-05。已完成一轮检索；上游规模不等于本地可运行规模。

## 数据与复制包

| 材料 | 已收集状态 / 固定版本 | 测什么 | 限制与许可 |
| --- | --- | --- | --- |
| [OWASP BenchmarkPython](https://github.com/OWASP-Benchmark/BenchmarkPython) | full_source_and_expected_csv；`f1291485808b66e20ddb6b01b10dc71b3df8c8ba` | 检测正负例、CWE覆盖、误报率 | 1230行=452正例+778负例、14类别；预期CSV和代码中的答案标记需隔离；未运行；GPL-3.0；历史：no local prior execution found; source exposure still needs audit |
| [RealVuln](https://github.com/kolega-ai/Real-Vuln-Benchmark) | metadata_and_2_full_target_sources；`7a710251f55c17d32d3adcb13d37468e2e3b9e4a` | 项目级发现、业务逻辑漏洞、安全负例 | 发行宣称140项目，实际只取Flask和DVNA完整源码；manifest 3.1.0与README 3.0.0不一致；教育项目非自然CVE总体；其他告警需复核；Apache-2.0 framework; DVNA MIT; Flask target license unresolved；历史：labels viewed earlier; full target source newly collected |
| [Tencent VulnGym](https://github.com/Tencent/VulnGym) | complete_annotation_files_not_target_repositories；`cd69f7e163e08485ab5496115ae03439cda6e27e / v0.1.4` | Agent主动取证、入口/危险操作/跨模块路径定位 | 184报告、408入口、393人工确认；不含23仓库完整源码；官方评分是覆盖/召回而非precision；模型不得读取trace；CC-BY-4.0 annotations; upstream source licenses separate；历史：earlier annotations collected; copy with provenance, not a new blind set |
| [SastBench](https://github.com/RivalSecurity/sastbench) | complete_original_json；`b8d95b7720491b21d039b7504999577ba7ebb12b` | 告警复审、误报过滤、弃权校准 | 2737告警=299TP/2438近似FP；Py/JS/TS候选1313项仍需语言审核；不是从零发现召回测试；只允许to_analyzer进入模型；Apache-2.0 benchmark; upstream projects separate；历史：earlier metadata and subset collected |
| [CrossCommitVuln-Bench](https://github.com/motornomad/crosscommitvuln-bench) | full_benchmark_archive_not_target_repositories；`e544e645fe164d62e5cbd5241ad49707ea786c73` | 跨模块组合缺陷与增量锚点研究 | 论文15CVE+6排除项；当前55完整项中的新增40项待人工复核，不能合称论文黄金集；当前平台不实现跨提交图；CC-BY-4.0 annotations; MIT scripts; upstream separate；历史：original 15 annotations viewed earlier |
| [OpenSSF CVE Benchmark](https://github.com/ossf-cve-benchmark/ossf-cve-benchmark) | fixed_metadata_archive；`91c59fd54b2b768c0f310bb0027d2ac59cdf74d4` | 自然CVE修复前后定位、规则外推 | 223个CVE元数据；元数据不等于完整项目。部分已用于旧pilot，应按repo/CVE排除；MIT metadata; upstream separate；历史：previous development source |
| [6个新增JS项目配对快照](https://github.com/ossf-cve-benchmark/ossf-cve-benchmark) | 6_complete_pre_post_snapshots；`12 fixed source commits recorded in local manifest` | 同目标根因的发现/规则/修复候选集 | 6/6双快照完整；已排除旧20-pair pilot仓库；未完成全部历史暴露检查、oracle/根因校准、输入去标签；不能称已认证安全负例；each snapshot retains upstream license; review pending；历史：not run; candidates, not certified untouched holdout |
| [SecBench.js](https://github.com/cristianstaicu/SecBench.js) | complete_framework_and_600_test_entries；`5d362353550a8baa42bba34edd26e5fb86d41b60` | JS偏门包/CWE、回归规则、单元级安全验证素材 | 600项、278含fixedVersion、573含sinkLocation；npm依赖包源码未下载；测试尚未运行；安全测试不等于业务功能测试；no standalone license found; local research, no redistribution；历史：no prior local run found |
| [SecJS / ForgeJS / JudgeJS](https://github.com/SecJS-Vuln-Benchmark/SecJS-Benchmark) | framework_metadata_only；`1bda0329805128bebb6581012642233a75c1c515` | 项目级标注和评分方法参考 | ArenaJS数据未公开在仓库；不计为已收集可测项目；Apache-2.0 framework; upstream separate；历史：earlier framework mentioned |
| [eyeballvul](https://github.com/timothee-chauvin/eyeballvul) | fixed_heads_directory_metadata_only；`framework 76a5d6c6ee7257fad10846934ab8863f60b52eff; data 288b718adda4f001425da5ffe65af74a166545f1` | 按漏洞公开时间拆分和持续新CVE候选 | 上游39981漏洞/13093快照/10005仓库不是本地下载量；仅heads/根目录/年月份tree及info日期字段，不含完整漏洞记录或项目；递归tree超15MB失败，废弃响应已清理；训练截止未确认；MIT framework; data/upstream terms require separate review；历史：new metadata; not evaluated |
| [VICBench](https://arxiv.org/abs/2608.12246) | paper_only_dataset_unverified；`arxiv v1` | 引入漏洞提交识别、历史切片方法参考 | 论文100条VIC/88项目，不是本地已下载样本；未确认公开数据下载入口；paper local reading only；历史：not evaluated |
| [Vulnerability Localization Benchmark (VLoc Bench)](https://github.com/cisco-foundation-ai/vulnerability-localization-benchmark) | online_primary_source_verified_local_download_failed；`not locally frozen; do not use mutable main for an experiment` | Agent全仓库文件定位及修复前后对照 | 官方500任务/290仓库，文件gold来自patch而非精确根因；给定CWE不是完全无提示发现；post标签不代表整项目安全；需区分超时/拒绝与真负例；本轮未下载manifest/项目；Apache-2.0 framework; upstream source licenses separate；历史：not evaluated |
| [VEX-Bench](https://github.com/steven1518/vex-bench) | online_primary_source_verified_local_download_failed；`not locally frozen; do not use mutable main for an experiment` | 供应链漏洞可达性与配置/环境证据复审 | 75案例/67CVE/35项目为上游规模；任务给定依赖CVE，不是新漏洞发现；Python需筛选，JS不覆盖；数据/完整项目未下载；not locally verified; inspect official LICENSE before redistribution；历史：not evaluated |

## 论文与专业来源

正式论文、预印本及官方技术报告分别标注；同一工作不同版本不重复计算。

| 文献 | 年份 / 状态 | 价值与核实机构 |
| --- | --- | --- |
| [SastBench: A Benchmark for Testing Agentic SAST Triage](https://arxiv.org/abs/2601.02941) | 2026；arXiv preprint | 复审任务与正负分布；not verified |
| [RealVuln: Benchmarking Rule-Based, General-Purpose LLM, and Security-Specialized Scanners on Real-World Code](https://arxiv.org/abs/2604.13764) | 2026；arXiv preprint | 项目级扫描器比较；原论文26 Python与当前140项目分开；not verified |
| [VulnGym: Benchmarking Coding Agents for Repository-Level Vulnerability Detection](https://arxiv.org/abs/2608.02001) | 2026；arXiv preprint | 端到端发现与oracle定位/证据子任务；Tencent and academic collaborators verified from repository |
| [CrossCommitVuln-Bench: A Dataset of Multi-Commit Python Vulnerabilities Invisible to Per-Commit Static Analysis](https://arxiv.org/abs/2604.21917) | 2026；AIware 2026 acceptance stated on arXiv/official artifact | 跨提交组合漏洞；not verified |
| [Large Language Models Cannot Reliably Detect Vulnerabilities in JavaScript: The First Systematic Benchmark and Evaluation](https://arxiv.org/abs/2512.01255) | 2025；arXiv preprint | 完整项目、标签和稳健性；not verified |
| [SecBench.js: An Executable Security Benchmark Suite for Server-Side JavaScript](https://github.com/cristianstaicu/SecBench.js) | 2023；ICSE 2023 mature benchmark | 可执行安全回归素材，非2026论文；not verified |
| [VICBench: A Multi-Language Benchmark for Code Vulnerability Detection](https://arxiv.org/abs/2608.12246) | 2026；arXiv preprint | 历史任务，非当前主测试；not verified |
| [eyeballvul: a future-proof benchmark for vulnerability detection in the wild](https://arxiv.org/abs/2407.08708) | 2024；arXiv preprint; current artifact updated in 2026 | 时间分割；旧方法文献补充；not verified |
| [Vulnerability Localization Benchmark: Measuring Agentic Security Analysis at Repository Scale](https://cisco-foundation-ai.github.io/vulnerability-localization-benchmark/technical-report.pdf) | 2026；official technical report; no peer-reviewed venue verified | 定位与修复版克制；官方部分失败计TN需单列；Cisco Foundation AI / Yale / CMU，官方报告/发布说明 |
| [VEX-Bench: Benchmarking LLM Agents for Assessing Exploitability of Software Supply Chain Vulnerabilities](https://arxiv.org/abs/2609.08040) | 2026；EMNLP 2026 acceptance stated by official project and Red Hat; proceedings forthcoming at collection date | 可达性、配置、环境的证据标签；不是端到端新漏洞发现；Red Hat / Purdue，官方发布说明核实 |

本地路径及下载状态见同名 JSON；逐文件校验见 `../manifests/local-integrity.json`。所有 raw/论文仅本地保存，未加入 RAG。
