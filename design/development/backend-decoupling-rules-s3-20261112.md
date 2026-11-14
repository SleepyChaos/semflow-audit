# S3 规则双入口：现有操作与科研契约映射

S3 | 2026-11-12T15:50:00+08:00 | in_progress。范围仅当前 RAG 方法与已有工具/检验集，不建立新实验或 holdout 平台。S1 极简 native 命令已另行补齐。

| 现有操作 | 科研输入/输出 | 平台边界 |
| --- | --- | --- |
| RuleGenerationForm → 新建 rule 阶段 | RuleGenerateSpec：源码/确认目标、CorpusSnapshot、检索/方法参数、RuleToolchain、StaticBaseline、已有 HoldoutHandle；RuleResult + 必要 refs | 先验证权限/最新确认，冻结输入；将科研规则映射为原 RuleVersion/样例/检索/查询 DTO |
| 图生成、编译、开发样例与项目重放 | 复用 RuleSynthesis / LangGraph；检验分别为 development_checks、project_replay；保存实际 QL/模块/依赖/fixture/日志/SARIF | 不在桥接内重新生成、编译或执行查询；CWE/位置相近只提供待确认线索 |
| approve-fixtures → resume | ApprovalRequest/Decision/ControlCommand 绑定 query/modules/dependencies/fixtures/最新 checkpoint 与 revision；从原图继续 | approve_stage 记录平台人工理由和科研控制命令；run_stage(resume=True) 走 research resume，不转 legacy |
| 批准后生成样例与独立检验 | technical_validation 与 independent_validation 分离；不选 holdout 为 not_evaluated/draft；已有隐藏微样例仅在批准后由 evaluator 读取 | 生成样例通过不等于独立检验，更不等于允许发布；发布仍检查人工批准、最新目标、源码/工具/结果身份 |
| confirm-project-match | 读取不可变重放结果/身份，不修改科研历史；模型未提供根因确认 | 保留人工目标根因/路径确认与基线排除理由；显式转换平台与科研的 ID/旧 source hash |
| query 下载、列表、publish / retire | public 读取已发布科研收据重建旧视图；独立 validate 仅接收已冻结的 query/fixtures/批准与工具输入 | 所有权、发布/停用与状态投影属于平台；core 不写平台 RuleVersion |
| 独立 CLI | 极简规则输入装配、generate / inspect / decide / resume / 必要 validate；复用 public actions/runs | 不依赖 app/ORM/Web/Celery；不要求手写内部 refs、ID、hash 或 Python 胶水 |

代码边界：算法留在 research/rules 与 graphs；外部 CodeQL、RAG 保留 adapters；runtime 只做冻结 codec/控制/产物；research_bridge 只冻结平台输入、映射身份与投影；services/stage_actions 与 rules 路由保留权限/人工/发布。历史未绑定 checkpoint 保留原执行器。

关键语义：RuleService 不再以“未选 holdout”作为 validated 条件；RuleResult 明确暴露独立检验收据。没有独立检验仍为草稿，不能从 CLI 的省略参数推导 Web 可发布。项目重放读取实际原始数据库及源码归档，使用显式 original_source_root 核对重定位后的文件；缺失/版本不符/解析失败必须失败。批准或恢复时修改查询、模块、依赖、fixture 或检查点会被拒绝；重复消息不重做生成。

验收按“生成与投影 → 双端批准恢复 → 原有检验/发布门 → 同输入对照”顺序推进。各小步只记录其实际范围；S3 四列齐全前保持 in_progress。
