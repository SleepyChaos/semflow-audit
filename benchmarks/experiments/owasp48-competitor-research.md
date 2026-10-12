# OWASP 48 例循环实验：竞品与论文比较准备

日期：2026-10-07。工作范围：核实公开一手资料、检查已固定阿里源码、制定真实竞品执行和计分边界；本文件没有新增模型实验成绩，也没有运行模型、目标服务、利用脚本或 GUI。

## 1. 本轮可以做什么比较

| 对照 | 本轮定位 | 同榜条件与限制 |
| --- | --- | --- |
| CodeQL 当前平台默认套件 | 必做传统静态基线 | 冻结 CLI、Python pack、套件 SHA、同一匿名源码；当前既有是 python-code-scanning，不能把 security-extended 的作者值当成默认成绩 |
| CodeQL security-extended | 可另列配置 | 同一源码实跑，单独命名，不能和默认套件混合 |
| Bandit | 可直接本地实跑 | 使用已下载固定版本；保留 Python 版本、插件配置、逐文件解析错误 |
| Semgrep CE | 推荐追加传统基线 | 冻结引擎和规则 YAML；不能实时 p/auto 变动，也不能把 CE 说成商业 Pro |
| 阿里 Open Code Review full scan | 推荐真实 LLM 竞品 | 运行官方固定源码的 scan 链路、默认模板和工具，接同一个模型；不是自制提示模拟 |
| 本平台独立 Scout | 必做内部 LLM 基线 | 同模型和源码，单独明确是否保留同样的任务清单、上下文补全 |
| 本平台 CodeQL + Scout + Review | 被评测方案 | D0/D1/D2/D3 分开报告，不能只展示最优阶段 |
| IRIS 官方 | 当前 Python 同榜不适用 | 官方发布围绕 Java；Python 移植需要另命名，不可冒充论文原系统 |
| RepoAudit | 可作为研究方法背景 | 原任务以数据流 bug 类型为主，Python 支持不等于现成覆盖 OWASP 14 类注入/配置；需固定实际审计策略 |
| ABSENTIA | 新论文背景 | 当前公开仓库只有 BAC-Bench，尚无可运行实现 |
| Frame | 备用真实新生代工具 | 支持 Python AI scan，但本轮尚未固定提交、安装和验证；其自报数字先放背景层 |

CodeQL 使用查询分析数据库并输出 SARIF；固定查询包和源码身份后适合静态配对比较。[官方查询分析文档](https://docs.github.com/en/code-security/concepts/code-scanning/codeql/codeql-cli)

Bandit 按 Python AST 插件检查常见安全问题，能以 JSON 输出；这不等于完整跨函数污点审计。[官方文档](https://bandit.readthedocs.io/en/latest/)、[CLI](https://bandit.readthedocs.io/en/latest/man/bandit.html)

Semgrep 支持本地 YAML 规则运行。商业 Semgrep Code 有额外的框架、跨文件和跨函数分析能力，CE 结果只能代表本次 CE 配置。[本地规则运行](https://docs.semgrep.dev/running-rules)、[Python 能力说明](https://docs.semgrep.dev/languages/python)

## 2. 阿里竞品：已核对的最小真实执行方式

### 源码身份和环境

- 本地源码：`/Users/chaos/Documents/Codex/2026-09-29/xin-j/work/open-code-review`。
- 固定 commit：`a758d9cbfb689937c7857ad64b2dd66adb58c0c2`，检查时工作树干净。
- 模块：`github.com/alibaba/open-code-review`，go.mod 要求 Go 1.25.5；本机 Go 1.26.2。
- 已离线编译固定源码，仅运行 help/零模型 preview；没有进行 API 连通性/工具调用兼容性实测。
- 检查时 `/Users/chaos/.opencodereview/config.json` 不存在，因此该用户配置目前不会抢占环境变量或注入 MCP。
- 官方有 full-file `ocr scan`，不需要造 git diff 或执行被审计项目。[官方仓库](https://github.com/alibaba/open-code-review)

### 官方入口与配置

从固定源码编译：
```sh
go build -o /absolute/artifact/path/ocr ./cmd/opencodereview
```

在子进程环境内设置 `OCR_LLM_URL`、`OCR_LLM_TOKEN`、`OCR_LLM_MODEL`、`OCR_LLM_PROTOCOL=openai`、`OCR_LLM_TIMEOUT`。URL 使用已授权 OpenAI-compatible base URL，token 仅在内存中读取既有配置，不写入命令日志或报告。生产环境存在用户配置时须先核实解析优先级及模型，不修改用户全局设置。

注意：**没有 `--tool-config` flag**；`--tools` 是工具定义数组文件，不是 endpoint JSON。源码 `shared.go:238` 和 `resolver.go:97` 先加载默认用户配置，再解析 endpoint；不传 provider 时顺序为配置、OCR 环境、Claude 环境、shell rc。

零模型预览：
```sh
ocr scan --repo /absolute/model-only/sample-root \
  --path "testcode/CaseA.py,testcode/CaseB.py" \
  --preview --format json --output /absolute/artifact/path/preview.json
```

真实审计（实际路径列表必须来自该轮无标签 manifest）：
```sh
ocr scan --repo /absolute/model-only/sample-root \
  --path "<48个固定案例文件的逗号分隔列表>" \
  --model deepseek-v4.1-flash \
  --concurrency 3 --timeout 10 \
  --max-tokens-budget <预先冻结的总token上限> \
  --format json --output /absolute/artifact/path/ocr-result.json
```

保持默认 planner、单文件 review、dedup、summary 和官方模板。不把本平台 review prompt 注入竞品，也不关闭竞品环节后仍称“默认完整竞品”。源码的 `--background` 可接受统一、非黄金信息的安全审计要求；若要求显式 CWE 编号，必须在全部盲测开始前冻结，并披露此配置适配。

### 工具、范围和预算差异

- 固定 core registry 为 `file_read`、`file_find`、`file_read_diff`、`code_search`、`code_comment`；这些读取源码或记录评论，未注册任意 shell/写文件工具。
- 本地 `scan_cmd.go` 使用该 core registry；默认无用户配置/MCP。模型允许读取的 repo 必须只含该轮 48 例与公共依赖，不能指向含 evaluator 标签/既有审计输出的完整研究仓库。
- 默认每文件最大工具轮数 60；`--max-tools` **只能提高**默认值，不能压到平台调用上限。不能宣称不同工具轮数本身公平；比较同 token 上限，并记录实际请求数和超限。
- `--max-tokens-budget` 在调用前/调度前检查；并发中的请求、最终提交响应可能超过上限。须记录实际 input/output token、模型请求、失败/取消、外部总 wall time。预算耗尽不是安全结论。
- 输出 `LlmComment` 有 path、content、start_line、end_line、category、severity，**没有结构化 CWE**。SARIF 格式也不能凭空补出黄金分类。

### 输出适配必须先定

编译二进制：`artifacts/competitors/ocr`，固定提交离线build收据：`artifacts/competitors/ocr-build-receipt.json`。初次把input放在Git忽略的artifacts里，preview rc0却选中0例；该次收据已明确标失败，不能视为成功。修正为独立 `/private/tmp` 非Gitscope后，最新 `artifacts/competitors/ocr-preview-acceptance-01-final2/receipt.json` 验证 **48个case、reviewable_count48、model_calls0**。输入仅54个py：48case+app.py+5helpers，不含templates/README/LICENSE/标签，冻结源码未改。

可执行runner：`benchmark-data/experiments/owasp48/ocr_run.py`（200行）和`ocr_support.py`；默认preview，显式`--execute`才调模型：
```sh
.venv/bin/python benchmark-data/experiments/owasp48/ocr_run.py \
  --sample acceptance-01 \
  --output artifacts/research/owasp48/20261007-evolution/competitors/ocr-acceptance01 \
  --execute
```

参数冻结：并发3、token1800000、外围1800秒、模型HTTP90秒；保留官方plan/dedup/summary，使用官方background统一要求有依据的CWE-N，未告知案例黄金类型。模型配置仅从audit_settings到进程env；argv/receipt不含key或完整endpoint，捕获输出/导出session精确token脱敏，带URL用户凭据/查询参数的端点会拒绝而不打印。默认raw HTTP日志禁用。

真实执行会写用户 `.opencodereview/sessions/<临时repo编码>/<session_id>.jsonl`，须获得受管写权限/授权命令升级，不重设HOME。输出字段为 `comments`、`summary.input_tokens/output_tokens/total_tokens`、`tool_calls`、`warnings`、`session_id`、`retry_report`。特别是 **summary.files_reviewed只是选中数**；scan尚未接run manifest，runner从native session的`review_item_done/failed`核对48项，保存未完成unknown。`llm_request/response/error`恢复逻辑调用和已记录token；不代表所有HTTP retry尝试/中断在途用量均已观测。stdout、stderr、raw.json、parsed.json、session.jsonl、receipt.json分开保存，部分失败保留，不静默重试。

严格文件+CWE 成绩：只解析竞品正文中明确写出的 CWE，不使用预期标签、文件名/源码模式给竞品补正确答案；保留未分类数。

为了不让输出格式差异冒充检测能力差异，可以另做**统一盲审**：隐藏系统名和黄金标签，对所有方案的原始发现按同一规则匹配漏洞类型，再由 evaluator 计分。只能放辅助层，不覆盖原始严格指标；未实施就写“未实施”。

所有未完成文件、预算中断、无效结构、定位失败都保留，主分母仍是抽到的 48 例。成功处理但无目标发现才可以充当检测负预测；显式失败另报 unknown，不能称 TN 成功。

## 3. 2025–2026 论文中能核实的相关结果

### 国内：跨语言表征与误报，2026-04-30

China Telecom Research Institute 作者的 **How Code Representation Shapes False-Positive Dynamics in Cross-Language LLM Vulnerability Detection**，arXiv v1，Table 8 使用 OWASP BenchmarkPython v0.1 的 **1108 例：420 正、688 负、14 CWE**。122 个 AST 转换失败样例被排除，所有条件使用该可解析子集。

| Qwen3-8B 作者条件 | FPR | Recall | F1 |
| --- | ---: | ---: | ---: |
| Zero-shot / Text | .703 | .893 | .586 |
| Zero-shot / AST | .999 | 1.000 | .550 |
| C/C++ Text Pilot / Text | .858 | .976 | .578 |
| 同 Text Pilot 权重 / AST | .554 | .698 | .536 |

论文二分类只看 found，不要求正确 CWE；模型/训练/子集/上下文均不同，不能与本轮48例精确 CWE 减分称提升。其启发是：AST 不会自动带来增益，应检查 FPR 和召回损失，而非只看 F1。[论文 §4.6/Table 8 与 §4.1评分](https://arxiv.org/html/2604.27714v1)

### 国外：ABSENTIA，2026-10-01

**ABSENTIA: Detecting Broken Access Control Vulnerabilities in Web Applications**，arXiv v1，另测 OWASP Python **10类注入、677例（240正、437负）**，Figure 5/Table 8：

| 作者完整系统模型 | Macro TPR | Macro FPR | Macro J |
| --- | ---: | ---: | ---: |
| MiniMax-2.5 | .85 | .42 | .43 |
| Claude Sonnet-5 | .95 | .14 | .81 |

较强模型账单6.2倍。不能把 macro TPR/FPR 转成全14类 micro F1。作者还给 Python 重实现 IRIS，不能当官方 Java IRIS直接支持Python。该方法启发是系统覆盖请求入口、验证权限属性与防止未经依据的业务策略推断；本轮OWASP不能单独验证真实业务权限发现。[论文 §7.1/§7.5/Appendix B](https://arxiv.org/html/2610.00977v1)

截至核实时，官方仓库只发布 BAC-Bench；实现计划2026年底，故不可在本轮伪造该竞品实跑。[作者仓库当前发布状态](https://github.com/avduarte333/Absentia)

### IRIS / ICLR 2025

官方论文是 **120个 Java CVE**，CodeQL检出27，IRIS+GPT-4检出55；用于研究 source/sink 建模与路径复审。语言、现实CVE分母、近似误报口径均不同，只作方法背景，不计算本平台超越幅度。[论文v3](https://arxiv.org/abs/2405.17238v3)、[官方实现](https://github.com/iris-sast/iris)

### RepoAudit / ICML 2025

原论文在15个现实系统找到38个真bug，Claude 3.5 Sonnet，平均0.44小时、2.54美元/项目；不是 OWASP Python全榜。当前官方仓库宣称 Python 支持，但需匹配实际 bug 类型/策略；方法背景不能替代本轮实跑。[论文](https://arxiv.org/abs/2501.18160)、[官方代码](https://github.com/PurCL/RepoAudit)

## 4. 新生代产品自报数字：单独列，不作为本轮实跑

| 一手作者来源 | 公布的Python成绩 | 当前可信边界 |
| --- | --- | --- |
| Frame | OWASP macro J 80.9% | 官方README自报；支持 `frame scan --ai` 和OpenAI-compatible；固定提交/输入/原始收据尚未核齐 |
| Cyfendo | 1230例；TP407、FP27，Recall90.04%、Precision93.78%、FPR3.47% | 厂商2026年9月扫描自报；不是独立复现或同48例预算对照 |
| VyQL | 1230例；TP452、FP99、TN679、FN0；macro J .8959 | 作者公开结果自报；含基准驱动开发过程，通用性/规则暴露要独立检查 |

来源：[Frame](https://github.com/lambdasec/frame)、[Cyfendo](https://cyfendo.com/benchmarks)、[VyQL](https://github.com/vyprai/vyql/blob/main/benchmarks/RESULTS.md)。

不能省略比平台当前分数更高的外部自报结果，再称平台“综合领先”；也不能把自报分数混入同机实跑排名。

## 5. 横向报告与停止条件建议

1. **同48例实跑表**：每轮同一份manifest对所有工具；主表TP/FP/TN/FN、P/R/F1、FPR、macro J、各CWE覆盖、未完成、wall time、token、调用。无法按CWE计分的发现另列，不从黄金标签猜。
2. **配对机制证据**：旧/新平台同48例同模型同预算；看错误去向而非累计成功并集。改后的下一48例为新验证，旧轮复跑只作回归。
3. **泛化证据**：不使用Case编号/黄金标签/修复答案触发分支；源码位置变换、分支/防护负例和跨框架自然CVE作独立验证。OWASP不同案例之间模板接近，换48例不是天然独立泛化。
4. **速度**：静态缓存重评分不是静态实际扫描速度，响应重放不是LLM审计速度；同机新扫描/相同冷暖缓存分别计时，所有模型阶段和失败重试计入。
5. **背景表**：论文、厂商自报用其原分母/指标，列版本、模型、允许输入、语言、计分和预算差异；不算跨榜差值。
6. **综合优势**：相对明确基线在准确度/误报/未决与成本延迟之间出现可解释优势才作有限结论；若结果未达到、边际提升消失或预算耗尽，报告限制和剩余缺口，不靠无限循环或挑选幸运样例制造优势。

机器可读来源身份及不能直接排名的理由见同目录 `owasp48-competitor-sources.json`。本文件与manifest无秘密配置、API key或目标源码。


## 实测状态更新（2026-10-08）

真实OCR已完成48/48，192请求，1509624 token，552.29秒；严格适配TP21/FP12/TN12/FN3，85条无明确CWE评论保持未分类。CodeQL、Bandit与平台新旧验收也已实跑；最终口径与限制以owasp48-final-comparison.md为准。前文“研究/预览”描述是执行前状态，未被当作真实成绩。
