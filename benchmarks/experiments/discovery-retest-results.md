# 漏洞发现整改与同项目复测

日期：2026-10-05；最终批次 `artifacts/research/discovery-retest/20261005-v2`。只处理发现/复审，未改修复或规则生成链路。

## 1. 结果

主比较使用同一源码、原CodeQL结果和原Scout候选池，模型仍为deepseek-v4.1-flash。每项目复审上限保持 **12调用、100,000 tokens、240秒**；实际输出上限仍6000 tokens。没有触发24调用覆盖测试。新Scout另跑，避免候选变化污染复审配对。

| 项目 | 原候选数 | 原已复审→新已复审 | 原未复审→新未复审 | 新supported/insufficient | CodeQL未匹配、复审新增支持主根因 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Flask | 16 | 4→16 | 12→0 | 14 / 2 | 2 |
| DVNA | 43 | 0→43 | 43→0 | 15 / 28 | 2 |
| 合计 | 59 | 4→59 | 55→0 | 29 / 30 | 4 |

29条supported建议归并至 **16个既有标注的主根因**（Flask7、DVNA9），其中4个原CodeQL未匹配。原候选池的主根因并集也为16/31，因此当前改进将这批已发现线索推进到了源码层面的模型支持，而没有扩大这批候选池的上限。

**边界：** 这是两个已暴露开发项目的一次配对复测，根因关联沿用既有源码辅助暂定裁决。supported是模型建议，未变成人工confirmed；未执行利用或服务，完整precision/F1未计算。两个未映射supported建议保留unknown，不视为新增TP。没有已知正根因被建议excluded，但本轮没有excluded建议，不能据此推断全面排误报能力。

统计：[discovery-retest-summary.json](discovery-retest-summary.json)；原始记录：[最终运行目录](../../artifacts/research/discovery-retest/20261005-v2/)；首轮不充分整改结果：[v1](../../artifacts/research/discovery-retest/20261005-v1/)。没有覆盖原校准记录。

## 2. 四个新增支持根因

| 项目/上游根因ID | 源码条件 | 本轮确认范围 |
| --- | --- | --- |
| Flask / 009 | app.py:15提交固定session-signing secret | 源码硬编码秘密；不证明实际部署cookie伪造 |
| Flask / 010 | String密码列、注册直接持久化原始表单密码、登录明文比较 | 源码明文凭据处理；不要求先证明数据库可被读取 |
| DVNA / 007 | forgotPw/resetPw对用户存在与否给出不同响应 | 源码用户枚举条件；未启动服务 |
| DVNA / 008 | resetPw/resetPwSubmit用md5(login)作为重置token | 源码可预测token与密码修改条件；未执行账户接管 |

相应理由、checked_premises及原根因关联均保存在统计JSON。捆绑debug次条件不加入主根因总数，沿用前一批严格计数规则。

## 3. 三个问题怎样修正

### 读取超限和坐标错误

- read_source先做路径/范围检查，最多151行，超过范围自动返回首分页、真实返回窗口和next_start_line。每页也按正文大小限制，不伪装读取完整文件。
- 坐标错误返回可纠正观察；路径逃逸仍拒绝。无有效证据不推断安全。
- 小目标模块以真实分页预读、同批共享，避免反复请求已经提供的代码。原证据留在数据库；模型引用本轮实际页的ID。
- 第二轮两个项目均没有超窗或incomplete批次。

### 覆盖调度和Flask证据不足

- 明确记录候选数、计划批次和可覆盖数量，优先审查Scout线索；将余下调用额度分配到未审批次。
- 最后一轮/重复读后使用final-only响应契约，要求给出结论或具体不足，不通过无限读耗尽预算。
- 新复审将源码必要前提与runtime_unknowns分开；不会把假设的WAF、外部数据库加密、生产部署当成已经展示的硬编码/明文处理缺陷必须满足的前提。
- 真正缺失的调用、guard、对象归属或实现仍保留insufficient。本次30条不足没有被强行改成supported。

### rp()误报陷阱

- 增加Python AST符号绑定线索，识别导入别名、函数参数、内建遮蔽、星号导入/动态环境未知。不把同名函数直接当危险API。
- 未绑定直接调用不能被支持为命令/代码注入；新Scout将无绑定注入假设保留为原始待核查观察，不进入可执行注入候选。
- 原两条rp候选本轮均为insufficient，没有supported。新Scout在该位置只留下 **unknown符号/行为问题**，明确说明rp未绑定到popen，未产生CWE-78命令注入候选。
- 这不表示整个lookup安全，也不是运行期可达性证明；动态注入或框架行为没有源码证据时仍未知。

## 4. 实现与测试

新生产入口使用review.v6、scout.v3；旧提示文件和旧阶段记录保留。主实现：

- [分页与小模块预读](../../system/backend/app/services/review_tools.py)
- [Python绑定线索](../../system/backend/app/adapters/python_bindings.py)
- [候选证据组织](../../system/backend/app/services/review_pool.py)
- [复审调度与结论反馈](../../system/backend/app/services/unified_review.py)
- [危险调用支持门槛](../../system/backend/app/services/unified_review_results.py)
- [粗筛绑定待核查观察](../../system/backend/app/services/scouting.py)

**50项普通回归测试通过，修改文件Ruff通过。** 新测试涵盖真实多页读取、坐标恢复、范围逃逸拒绝、43候选在12调用预算下分配、未绑定危险调用、内建遮蔽及旧流程恢复/候选历史。测试文件：[test_review_recovery.py](../../system/tests/test_review_recovery.py)。没有GUI或目标服务测试。

两个目标源码哈希与原静态快照一致，最终运行期间实现哈希未变化；收据：[integrity.json](../../artifacts/research/discovery-retest/20261005-v2/integrity.json)。新审计历史记录与旧记录分开，不重复运行原CodeQL扫描；它们的源码/pack/suite均不变。

## 5. 速度、代价与覆盖限制

| 复审阶段 | 原耗时/调用 | 新耗时/调用 |
| --- | --- | --- |
| Flask | 29.27秒 / 7 | 27.28秒 / 4 |
| DVNA | 7.29秒 / 5 | 59.81秒 / 11 |

DVNA耗时上升对应0→43候选完成复审；原快速结束是失败，不能作为相同质量速度基线。这里是复审阶段墙钟，未测真实并行端到端延迟。

新独立Scout：Flask检查4/4窗口；DVNA在固定粗筛预算下只检查5/18窗口。**候选池复审完成不等于整个项目已充分扫描。** 扩大独立粗筛业务流程覆盖仍是后续工作。

第一轮整改v1先解决分页/排队，但仍被重复读取、沿用外部前提和预算消耗卡住，未复审Flask12、DVNA39；因此继续修成v2。首轮44次文本调用、最终轮34次，共78次本次调用，全部保留；没有只保留最好结果。

## 6. 下一步

当前三个指定问题已完成整改并有同项目回归证据。接下来先独立复核4个新增支持与两个未映射支持建议，再扩大未充分检查的DVNA窗口和跨项目开发集。只有冻结同版本/子集与官方评分口径后才进行论文比较。本轮不声明超过RealVuln论文或整体精准率提升。
