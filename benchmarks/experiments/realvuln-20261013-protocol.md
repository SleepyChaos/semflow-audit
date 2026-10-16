# RealVuln 论文 26 项目双链路协议

日期：2026-10-13。任务：在当前平台版本上，对论文中的全部 26 个 Python 项目运行单 CodeQL 与综合审计，对照作者已有结果。

## 冻结输入

- Hugging Face `Kolega-Dev/RealVuln/tree/v1.0.0` 当前连接失败，使用作者官方 GitHub 仓库历史作为来源，不声称已验证 HF 字节级一致性。
- GitHub `v1.0` 指向 `d98e9fc91273702c9547663b6906d1fc494d4fcc`，标注已增至 697 漏洞，不能直接替代论文 676 的分母。
- 使用历史 `55350cdc0f0f7db85d1f0b97649df07e6d63c665`：26 项目、676 漏洞、120 FP traps；项目 URL/commit 清单与后来 v1.0 的 26 项清单相同。以固定 commit 获取源码，不允许 checkout 失败后使用 HEAD。
- 个别仓库 URL 已失效时，可使用作者后续版本提供的仓库 URL，仍要求 commit 完全相同。获取尝试与实际 commit 写入独立收据。
- 使用官方 v1.0 scorer，包含论文说明的 acceptable-location 支持；将作者保存的 scanner 输出按相同标注重新评分。Semgrep、Snyk、SonarQube、Sonnet、Gemini、Kolega 的结果复现论文主表至显示精度附近。
- 标注、描述、PoC、作者 scanner 输出仅保存在 evaluator-only 目录；生产模型只能读取独立 sources 下目标仓库原始文本。仓库自身的注释、文档和测试保留，未做语义改写；这是故意带漏洞的教育项目输入，不能外推为自然 CVE 分布。
- Flask 项目在本仓库历史中已用于开发校准，本轮不是整个数据集的独立盲测；没有基于本轮标签修改产品规则或提示。

## 两条链路

1. **单 CodeQL**：当前生产抽取/扫描适配器、CodeQL 2.23.5、`codeql/python-queries@1.6.0`、`python-code-scanning.qls`，无自定义规则、无 LLM。每个项目构建一次数据库并查询一轮。
2. **综合审计**：同一源码和同一 CodeQL 输出，加独立 Scout v7、统一 Review v12。通过实际生产 LangGraph/services/provider 与数据库执行；模型为本地配置的 `deepseek-v4.1-flash`，无测试替身。默认预算保持不变，每个阶段最多 24 次调用、100000 tokens、300 秒；粗筛最多 24 窗口，默认跳过第三方窗口；复核最多 24 批、每批 4 候选、最多 8 步。provider 自身的输出保留量和结构修复会进一步约束可调用次数。

静态输出在两条链路共享一次，以减少重复的确定性扫描；Scout 不接收静态告警。实验执行顺序是 static→scout→review，项目并发 2。因此报告的阶段时间和顺序总时间不等于产品 UI 的双引擎并发延迟。不自动修复或生成新规则；本轮测试是漏洞发现与复核能力，而不是修复正确性或规则生成能力。

生产代码在 `artifacts/research/realvuln/20261013-paper-v1/implementation/` 冻结。每项目执行前后校验源码与实现哈希。使用独立研究 owner、audit 和 stage ID，与现有任务隔离。直接注册研究审计绕过 ZIP 上传限制和 GUI；OWASP Web Playground 超过 2000 文件，必须单独披露这点，不能称上传端全链路验收。

## 输出与评分

主表：

- `codeql`：全部实际静态告警。
- `system_supported`：实际生产复核通过结构与证据门的 `supported` 候选，即当前 v12 的 AI 确认输出；不等于独立人工确认。

辅助表：

- `system_retained`：保留未知、未复核和证据不足候选，仅移除经生产门验证的 `excluded`；用于说明主表没有把未知判为误报。
- `raw_union`：静态告警与粗筛候选直接并集，用于查看复核前后变化，不冒充最终系统成绩。

使用官方 matcher：相对文件路径、acceptable CWE、位置 ±10 行；每个 GT 消耗一次，重复告警会成为额外 FP。CodeQL 使用 SARIF 主位置和真实规则 CWE 标签，按官方 Semgrep parser 的多 CWE 展开方式转换；未知 CWE 不默默删除，记为未匹配告警。AI 使用生产候选主位置与有效 CWE。绝不从标签反推 CWE 或改写告警位置。

全榜使用 strict micro：汇总 TP/FP/FN/TN 后计算 Precision、Recall、F1/F2/F3，F3 为论文主指标。执行失败状态单独记录；没有可用结果的失败项目在 strict 评分中计全 FN，但不标记为成功的空结果。阶段完成与覆盖完成分别统计，不能把 `completed` 当作全面审计。主表与辅助表均保留所有 26 项分母。

## 执行收据

- 首次冻结代码目录未继承真实查询包路径，26 次数据库抽取后因查询包路径不可用结束。失败记录保留于 `attempts/00-environment-path-error/`。
- 后续显式映射本地查询包和产物路径，核对源码哈希后复用对应数据库继续查询；没有覆盖首次失败记录，也没有替换模型配置或预算。
- `realvuln_prepare.py` 获取与冻结，`realvuln_run.py` 调用生产链路，`realvuln_score.py` 为独立 evaluator。新增适配器的正例、负例、重复告警、跨任务路径、未决保留、严格分母测试已通过。
- 原始目标源码、SARIF、模型响应、阶段证据和数据库位于 Git 忽略目录，不提交到 Git。公开报告仅包含聚合计数、版本与复现说明，不复制密钥。
