# 实验工作日志

按时间追加，进度以 [state.json](state.json) 为准。每次会话只写关键完成项、证据、决策、未完成项和下一步。

## 2026-10-05：收集完成后建立正式实验计划

- 已完成：三方向首轮检索与材料格式检查；本次新建总计划、首批项目选样、执行/恢复规程与任务状态。
- 材料证据：[收集汇总](../manifests/collection-summary.json)、[首轮检索报告](../search-round-report.md)。10908 个本地文件、28 个有效归档、6/6 个 JS 双快照；这些不是可运行任务数量。
- 决策：优先 OWASP Python、RealVuln 两个开发校准项目及六个自然 JS 配对候选；PatchEval/Vul4Py 修复候选先筛纯单元双 oracle。
- 决策：发现、规则、修复分开主实验；速度全程采集；RAG 检索与 QL 生成分开评价；只根据开发结果改实现。
- 决策：生产 suite 身份待 E00 核实，不能照搬旧脚本的 security-extended。修复产品不加入利用复测，不启动目标服务，不做 GUI 测试。
- 当前缺口：暴露审计、去标签、根因/oracle 校准、统一 runner、正式任务清单和预算均未完成。
- 计划校验：状态 JSON 可解析，13 个任务 ID 唯一、依赖无环，计划文件相对链接有效，正式运行次数为 0；仅做文档/状态校验，未执行产品测试。
- 本次停止位置：计划完成，尚未启动 E00 或任何新的模型/扫描/目标测试。
- 下一步：E00，冻结工作树、模型/提示/CLI/pack/语料身份，建立候选的历史暴露清单。完成后登记收据路径，再推进 E01。

## 后续追加模板

```text
日期 / experiment_id / task_id / batch_id：
完成项与 acceptance：
产物路径、hash 与完整性检查：
有效运行/失败/未决、已用与剩余预算：
决定及依据（是否改变实验版本）：
剩余项、暂停/延期原因：
下一项及准确命令/前提：
```

## 2026-10-05：首批校准测试完成，论文可比门槛尚未通过

- experiment_id：`20261005-calibration-v1`。完整静态目标8/9成功，Angular默认预算OOM；修正OWASP匿名loader后另存输入并重跑CodeQL/Bandit，旧结果留诊断。
- 核心工作流实跑：RealVuln两个开发项目粗筛+复审；systeminformation一个模块旧/新各三轮；两个Python QL任务三模式各三轮，共18次；独立20查询三模式。无GUI、无目标服务、无下游利用。
- 发现：严格主根因暂定线索12/31→16/31，最终新增supported=0；55候选未复审。修复：v1有界联合3/3、v2为1/3，两次上下文溢出。规则：5/18开发编译验证通过，5次隐藏评测全部TP=0；13次未进入隐藏，不伪造零分。
- 成本：99次文本调用，681097输入、99199输出tokens；独立embedding请求20次，生成embedding未完全汇总。付费批次已结束，不重跑。
- 完整性：12份静态输入快照与保存hash一致；产品backend hash未改变；修正OWASP 1236/1236文件提取、0 error通知；新评分/loader普通测试3 passed，Ruff通过。runner后期格式/汇总检查有独立hash，不覆盖原始config/runner-snapshot。
- 论文：8篇90行作者结果已从本地PDF核对。RealVuln版本、QLCoder语言/反馈、PatchEval/Vul4Py任务分母不一致，未宣称同榜提升。Bearer上游归档存在输入漂移及失败，拒绝填竞品成绩。
- 证据：[结果](calibration-results.md)、[机器统计](calibration-summary.json)、[论文对齐](paper-baseline-alignment.md)、[改进计划](calibration-followup-plan.md)、本地`artifacts/research/formal/20261005-calibration-v1/integrity.json`。
- 决策：校准先发现接入/上下文/确认门槛问题，再修正式任务；不把小批或未评估当正式榜单。正式run_count仍0，E06–E12保持planned。
- 下一步：E01输入去类别提示和入口等价检查；E02参考QL/人工oracle；E03恢复/隐藏隔离/任务隔离普通测试。随后按改进计划新run ID做开发集配对回归。现有批次没有待运行进程。

## 2026-10-05：追加失败溯源，不改原计数

- 只读取源码/原始产物，没有新模型调用。DVNA四批因非法窗口中断；4批×4候选预算也只能覆盖43候选中的16条。SQL五个有效草稿中3次资料槽错配NoSQL，原因是title.contains子串；五个QL query_hash一致，未补目标helper模型。
- 修复round1首次proposal45819字符超40K；round2首次38057、已应用真实差异补丁，却被诊断LLM错误判no-op；重试payload44046超预算。追加在同受限Docker内评测已有round2补丁，有界双oracle通过。原v2流程完成1/3保持不变，事后检查单列。
- 新证据：[失败溯源](failure-analysis.md)、本地posthoc/failure-analysis-receipt.json与repair-v2-round-2-existing-patch/oracle-result.json。下一轮增加诊断事实校验、unknown不误触发修复循环、结构化资料族筛选及候选覆盖预算。

## 2026-10-05：漏洞发现三个问题整改与两轮复测完成

- 新生产review.v6/scout.v3；分页恢复、覆盖预算分配、小模块预读、源码条件/runtime_unknowns分离、Python符号绑定检查和未绑定注入观察隔离。保持原候选历史与源码。
- 普通回归50 passed、Ruff通过。v1整改不充分结果保留；v2同池12调用/100K/240秒上限：Flask16/16、DVNA43/43已评估，未审均0，新增支持主根因2+2。supported非人工confirmed；2个未映射supported保持unknown。无扩大预算阶段。
- 新Scout单独跑：Flask4/4窗口、DVNA5/18；rp位置仅unknown未绑定行为观察，没有CWE78候选。候选复审完成不表示全仓库覆盖完成。
- 使用模型次数v1 44、v2 34，共78；未覆盖失败、未重复旧CodeQL扫描。源码快照/最终运行代码hash核对通过。无GUI/服务/利用测试。
- 证据：[整改复测报告](discovery-retest-results.md)、[机器统计](discovery-retest-summary.json)、本地artifacts/research/discovery-retest/两轮不可变收据。
- 下一步：独立复核新增与未映射支持，再扩大发现覆盖；论文同榜门槛仍待完成。当前没有运行中的测试进程。

## 2026-10-06 输入/检查覆盖整改启动

用户授权整改后复测。增加模板/配置输入、业务优先级和按安全属性的调查收据，生产Scout版本5；70项普通回归通过。测试导出器原ALLOWED遗漏EJS，生成独立新输入，DVNA新增55个模板/配置文件，原文件逐字节一致。最终批次20261006-v2分同预算粗筛和更高预算完整业务覆盖+review6；不扩展CodeQL套件，不更换模型，不做GUI/服务/利用测试。v4先导20261006-v1在完成Flask复审边界停止，保存长输出/上下文重复失败和全部费用；不得重跑旧付费阶段。

## 2026-10-06：输入与检查覆盖整改完成

- 最终汇总20261006-v6：复用v2 Scout5、v3单窗口恢复、v4/v5 Review7、v6未完成候选单次补测。Flask10/10、DVNA71/71业务窗口调查；4第三方/生成窗口默认延后；384安全任务记录含50 unknown，不称全部安全。
- 主条件去重并源码辅助暂定裁决：Flask10/14、DVNA14/17，总24/31；旧最终16/31，当前完整输入CodeQL13/31。完整配置扩大输入/预算，不能叫同预算或论文提升。模型76条supported不等于76真漏洞；未映射保留unknown。
- 原测试导出遗漏EJS修正，DVNA新增55模板/配置，旧文件字节不变；相同suite新增products.ejs:20 XSS根因与未标注CDN告警。这个新增不是Agent收益。
- v5原有4候选因反证漏引目标页而整批未审，v6明确引用合同后只补测这些身份+1重复静态控制，8调用、21.71秒、全部结论；不覆盖原unknown。DOM XSS支持，admin布尔插值排除；ping EJS语法颠倒误报已排除。
- 普通回归81 passed，引用合同追加定向1 passed，Ruff通过。无GUI/服务/利用。所有阶段各自输入/实现/提示快照保留；v4 runner误读启动元数据中断，新ID恢复未重复Flask。最终无运行中模型测试。
- 所有本阶段尝试按stage_id去重301文本调用，输入2290763、输出247846 tokens（53+154+45+7+34+8），失败与先导也计成本；旧99/78调用另列。
- 证据：[结果](discovery-coverage-results.md)、[汇总](discovery-coverage-summary.json)、[可重复裁决器](discovery_coverage_score.py)、artifacts/research/discovery-coverage/20261006-v6/root-adjudication.json。
- 下一步：先独立端点×安全属性、精确主定位、实际middleware/角色/日志本地取证，再相同输入预算及未暴露材料对照。正式金标门槛仍未完成，不自动重复付费批次。

## 2026-10-06：效果复核与语义/流程下一阶段设计

- 用户要求先核实改善，再分析已读仍判断错误与新流程问题。本次只读源码/原收据及普通代码诊断，没有生产代码修改或新模型调用。
- 已按静态ID+Scout持久化ID核实v3与v5完整候选池相同。review6和review7+受限补测严格主根因均24/31；DOM XSS升级支持，login限流转未决，Flask error模板排除转未决，ping EJS颠倒误报纠正。覆盖提升明确，语义净提升尚未证明。
- 普通诊断：调用位于第3行、主定位第2行时binding_clues返回无call；只用README证据可以提交authorization=investigated。没有将这些诊断算作新的真实漏洞或模型效果。
- 设计优先级：候选失败隔离与一次共享预算恢复；实际operation定位与独立安全属性；本地前提证据账本、版本资料与跨候选矛盾；固定同池预算配对。已重读本地IRIS §3.5/§5.5，不推断方法对当前模型自动有效。
- 产物：[语义/流程改造方案](../../docs/discovery-semantic-improvement-plan.md)、artifacts/research/discovery-coverage/20261006-v6/semantic-flow-diagnostics.json。本阶段方案完成，实现尚未启动；原覆盖改造已完成状态保持。


## 2026-10-07：语义与可靠性整改进行中

- 已实现 Scout6/Review8：精确源码引用定位、认证/授权/限流/日志属性、三项漏洞前提账本、小型本地入口/依赖源码预读、候选级证据失败隔离与同阶段预算内一次补审、完整性错误停止。50项针对性普通回归通过，Ruff通过。
- 20261007-v1模型输出将 protection=contradicted 理解为无有效防护，合同歧义造成拒绝。主动停止并保存失败/调用收据，未跑其后续阶段；中断请求用量可能未知，不删失败费用。
- 修正为unsafe_protection（漏洞成立条件）后，20261007-v2真实模型运行中。Flask同池复审13calls、有2未决复审条目；源码补充5calls；合池复审29calls、有5未完成条目。暂不据此报根因增益。发现跨窗口重复与端点捆绑，需要语法端点清单和窗口隔离；合同ID预读后刷新、补审输入具体拒绝原因待修。
- OWASP准备：结构检查1230文件与loaderCase集合，答案在工具根外，无expected CSV/金标进入输入；固定seed20261005抽56（28正28负，14类）。完整CodeQL缓存精确CWE adapter：138TP/150FP/628TN/314FN；56代表批9TP/3FP/25TN/19FN。不是官方scorecard，不与论文异制度数字求差。


### 2026-10-07：语义改进补测完成，启动OWASP代表批

- v3 26/31→v4 28/31；v5有效调查隔离、v6定位提示单独改造没有增加根因；v7一次真实源码行号反馈补到29/31。DVNA17/17、Flask12/14；两个rp未绑定标注保留证据不足。所有合并候选复审完成，未映射告警仍需人工裁决。
- 39普通回归通过。39/126合并候选，累计开发集结果不是单次完整扫描。271次持久化调用，2968438in/421568out，中断在途成本下限。完整文档discovery-semantic-results.md。
- 已启动OWASP56代表批14组、3并发，session28704。完整静态1230缓存，AI仅56例。严格标签隔离，不启动GUI/服务/利用；冻结实现和runner，完成后运行owasp_pilot_score.py写指标与未决明细。


### 2026-10-07：OWASP代表批完成并冻结评分

- 14组全部完成，56/56case窗口，105条任务unknown，4候选unknown。D0 TP9FP3/F1 .45；D1/D2 TP20FP14/F1 .6452；D3 TP14FP5/F1 .5957。151calls，1084620in/243583out，实际829.17秒。完整性通过，标签未进模型，未执行GUI/服务/利用。
- 复审合并结果漏计6个正例，其中4个仍supported但CWE默认unknown覆盖了检测类；其余XPath未完成、XSS前提冲突。CWE保存/未知分类不绕危险绑定/定位反馈超限保留发现三项补丁在冻结模型运行后实施，42普通回归通过，原分数不改。离线元数据反事实TP18FP5/F1 .7059，仅诊断，不能称新端到端结果。
- 标准CWE父子类不对齐、缺业务权限合同、辅助路径/分支语义和缓存效率仍待下一阶段。全量1230AI未运行，完整CodeQL1230仅缓存。主报告owasp-discovery-results.md；状态已更新，不再追加本轮付费测试。


### 2026-10-07：用户将验收改为标准基准上的通用收益

- 停止以RealVuln累计31/31追分作为主目标；该材料仅开发回归，v6/v7passport定向补测不能用于泛化声明。生产168文件未检出特定项目/case ID分支，仍存在入口命名/语言框架假设。
- 本次0付费调用，OWASP184候选池原180接纳裁决完整宿主重放，当前绑定/前提/引用门槛均通过，4unknown保持；分类保留使精确评分TP14→18 FP5/F1 .7059。目录/文件名、17空行、组合变换180/180均一致。确认工程机制可迁移，未证明新模型端到端发现泛化或审计提速。原模型/源码产物未修改。
- 新报告discovery-generality-review.md及协议discovery-generalization-protocol.md；后续对照旧/新平台标准基准同配置/预算，先预注册分类口径、校准独立材料和暴露分组，再检验业务合同/框架事实/路径语义。


### 2026-10-08：OWASP48通用循环与真实竞品验收完成

- 预注册种子2026100748，3批文件不重复48（24正24负、14类），排除旧56。6平台执行+真实OCR完成，候选在验收计分前选revision-01；labels未进入模型/RAG，源码/实现hash均完好，无GUI/目标服务/利用。
- 通用修订：AST本地导入/实际入口；条件化Flask语义；业务政策依据与缺保护分离；最终值/反证一致性和分组独立复审。Astroid4.3.3实验revision-02/dev02与rev01准确率相同但token+22%，留实验8/10，默认切Scout7/Review9。
- 验收CodeQL TP9FP2；Bandit TP3FP2；旧平台TP17FP3；新平台TP18FP2/P90/R75/F181.82；ScoutTP18FP10；真实阿里OCR TP21FP12/P63.64/R87.5/F173.68。新增CodeQL正例9、保留原9；合流复审减8FP丢1TP。符合预定有限优势，OCR召回更高，静态更快，不能全维度/全榜领先。
- 旧→新共用实测静态+各自AI阶段和444.83→472.40秒（非进程/GUI端到端），token1254559→1398171；配对3正确改善/1退化、p=.625。48case窗口完整，1unknown候选/99unknown任务，outside34、OCR85未分类评论未盲审。结果是严格目标CWE案例，不是逐告警真实准确率。
- 83相关普通回归通过，Ruff通过。全部已记录1047逻辑调用、8274746in/1525660out=9800406token；远端内部重试/在途未知费用不估零。preview失败零请求保留，未静默重跑付费阶段。
- 6FN/2FP验收后诊断：操作任务遗漏、过度业务前提、CWE差异、列表变更与固定路由约束。下一轮换预留数据，不能根据这48例补丁后重写本轮成绩。报告owasp48-final-comparison.md，机器统计owasp48-final-summary.json，state/progress和原始不可变收据更新。


### 2026-10-08：测试分为通用基准与专项同任务，统一统计材料

- 用户要求将测试分为A类通用基准、B类专项竞品同任务；三条能力作为标签，不设第三类。新入口test-programs/README.md，原始数据/已冻结结果未移动或改写。
- 合并三方向目录、旧研究书目、方法登记和近期竞品，32项材料候选：发现16、规则6、修复10；按主要用途通用13、专项19。不是32个独立可运行数据集。
- 去重文献登记43项，引用年2026计29、2025计12、历史2024/2023各1；25本地PDF文件对应21项文献，1项HTML全文，21项其余参考登记。QLM仅摘要；首次公开年与引用年区分，未称全部通读/复现。
- 主要外部对照10个、已有同OWASP48实跑3个（CodeQL、Bandit、阿里OCR）；另8个方法候选。官方自报、论文参照、方法重实现与实际复现分层，不合并排行。
- ABSENTIA官方仓库/数据说明/论文在线复核：BAC-Bench30条/25仓库/9框架，Py18/TS9/JS3；公开索引，不含目标源码副本，检测器计划2026年底发布。公共索引下载升级调用超时，未算本地下载；网页核验完成。详细专项计划保留目标根因召回、修复前后配对与统一盲审，金标路由/政策不得进入模型。
- 接入3例若完成则标开发暴露；之后全30作者参照另列未暴露部分。修复后只作为对应根因负例，未匹配新发现保持待审，不能将整仓库视为安全负例。
- current_test_inventory.py拆分静态登记到manifest，格式与Ruff检查通过，脚本已本地运行复核；229行，仅读元数据/文件，不执行目标源码。没有新增付费模型/GUI/服务/利用测试。
- 下一步只从state.next_action恢复：准备新通用预留样本与BAC-Bench固定索引/源码、隔离答案和裁决，规则与修复正式准入独立推进；本轮OWASP48冻结成绩保持。


### 2026-10-08：论文时效与外部对照覆盖核查

- web-access前置检查Chrome未连接，采用公开一手静态来源核查；没有GUI或目标服务测试。31条arXiv标题/首次公开/修订元数据核对，11条正式发表记录复核（有交集）。不是全部全文重读。
- 原43项/32材料/10外部工具统计保持，修正RepoAudit正式标题，文献表增加首发、最新arXiv版及已核准venue；Vul-RAG首发2024、TOSEM正式2026-09-16，两者分开。QLCoder2025首稿、ICLR2026与2026-08-26最新预印本分开。
- 新候选单列KeaRepair2026-07-01、AgenticRepair2026-07-31（TSE审稿中）、HowSafeAreAIGeneratedPatches2025-06-30（12-29修订）；未并入43项，未下载/复现工件。
- 文献够新，但实跑外部工具仍3个且偏发现；优先SemgrepCE、独立同模型Agent、PyJSQL外部生成器/隐藏金标及OpenHands修复联合oracle，ABSENTIA任务按既定源码/金标准备推进。
- OpenHands当前主仓库是AgentCanvas，Agent实现转software-agent-sdk；严格复现仍要固定Vul4Py作者runtime。新增候选OpenHands/SWE-agent、SonarQube/CodeRabbit不算已实跑。10-06CodeRabbit报告是内部开发切片的目标找回率厂商自报，不与OWASP48混表。
- 报告test-programs/freshness-and-coverage-review.md，机器记录manifests/freshness-and-coverage-review.json。统计脚本Ruff通过，重建统计不变；本次无付费模型调用或安装新竞品。

### 2026-10-08：LLM 与 CodeQL 深度协同研究建议

- 用户要求研究审计创新点的方法差异。本轮核查发现并行链路、已有发布规则 static_query 工具与窄范围 Python sink 模型；未把已有工具交互误报为完全不存在，也未视为通用模型精化已经实现。
- 定向阅读 IRIS、SemTaint、ARQ、LLM4PFA 的方法，及 Artemis、ABSENTIA、APAS-Finder 的相关机制；补查 CodeQL 模型/partial-flow 官方文档和本地固定 pack。SemTaint 已有按需调用图与第三方摘要精化；ARQ 已有独立运行时反例和累计回归；APAS-Finder 的语义事实依赖人工核验。
- 候选优先级：条件化且显式保留不确定性的分析模型精化；业务权限关系的 CodeQL 检查；受限路径约束核验作为组件。均为待验证研究假设，未声明首创或效果已提升。
- 文档：[协同研究建议](../../docs/research/codeql-llm-interaction-research.md)。168 行，引用本地源码路径已校验。对照/消融、条件迁移、模型误排真漏洞、未决和成本的评价边界已列出。
- 本次只增加研究文档和日志，没有生产改造、付费模型调用或 GUI/服务/利用测试。候选方案尚未确认为开发任务，state.next_action 的原实验输入准备保持；既有材料统计未变。

### 2026-10-08：细化 LLM 在 CodeQL 分析中段的介入设计

- 用户要求具体运行中段介入位置。细化固定诊断查询→语义需求→LLM 转换/保护事实→绑定核验→GlobalWithState→下一轮需求；查询之间注入事实，不宣称现有 CLI 支持谓词 HTTP 回调或内部暂停恢复。
- 本机 CLI 2.23.5 version 与 query run 帮助核查，支持 --external CSV。固定 Python NoSQL 和 JS prototype-pollution 库已有 StateConfigSig 状态转换/屏障真实用例；新增候选查询尚未编译实现。
- 明确旧状态边不会因新增转换边自动消失、模型变化须重新求值、原生查询不会自动使用外部模型、未知不直接作为安全屏障。语义转换/保护失效是拟研究对象，现有 FlowState 和外部谓词不是新贡献。
- 产物：[中段介入详细设计](../../docs/research/codeql-intermediate-llm-design.md)，文档引用与代码块结构已校验。只做接口/源码可行性核查，没有生产改造、模型调用或能力实验；原 next_action 保持。

### 2026-10-09：工作区迁移到 SemFlow Audit 私人仓库

- 用户授权将当前工作迁入 GitHub 目录并创建新私人仓库。新本地根目录 `/Users/chaos/Documents/GitHub/semflow-audit/`；项目、研究材料、环境与产物完整重命名迁移，原 work/outputs 移入忽略的 `.local-workspace/`，旧三个路径保留符号链接。
- 新仓库 `SleepyChaos/semflow-audit` 已创建，GitHub API 确认 isPrivate=true；旧远程作为 legacy-origin 保留。保留原有 Git 历史，最新未提交开发、文档与实验索引纳入迁移提交。
- 迁移前 627 个候选文件和当前分支历史 469 个 blob 的常见凭据格式检查无命中；暂存内容及忽略边界另行核查。原始测试源码、论文、评测答案、环境和 artifacts 仍只在本地。
- Docker 现有项目标签核对为 ai-code-audit；本地 .env 固定 Compose 项目名，并验证配置解析，继续沿用原数据卷。没有启动/重启服务、GUI 测试或新模型实验。
- [迁移说明](../../docs/workspace-migration.md)与[方案索引](../../docs/research/codeql-llm-proposals-index.md)更新。实验 next_action 和历史效果口径保持；今后从新根目录继续。
