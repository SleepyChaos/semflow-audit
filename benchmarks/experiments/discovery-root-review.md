# 双引擎首轮根因核对

日期：2026-10-05；run `20261005-calibration-v1`。

**本报告是 agent-assisted evaluator 的源码辅助暂定裁决，非独立人工金标。** 没有再次调用模型，没有把产品 LLM 的 supported/insufficient 当作真值。读取上游 gold、实际输入源码与已有 SARIF trace；未执行利用、服务或 GUI。两个 RealVuln 项目属于已暴露标签的开发校准材料。

逐根因、候选 ID、复审状态和文件哈希见 [root-adjudication.json](../../artifacts/research/formal/20261005-calibration-v1/discovery/root-adjudication.json)。保留所有未匹配告警为 unknown，不计算完整 precision/F1，不把下表叫作论文复现结果。

## 1. 已运行结果与暂定根因覆盖

| 项目 | gold 正根因 / FP trap | CodeQL 告警→gold 根因匹配 | Scout 假设→gold 根因匹配 | 两者并集 | Scout 新增匹配根因 | 产品复审新增 supported |
| --- | --- | --- | --- | --- | --- | --- |
| RealVuln Flask | 14 / 5 | 5→5 | 11→6* | 8* | 3* | 0 |
| RealVuln DVNA | 17 / 0 | 33→7 | 10→6 | 9 | 2 | 0 |
| 合计 | 31 / 5 | 38→12 | 21→12* | 17* | 5* | 0 |

\* Flask 一个候选捆绑“硬编码 secret”和“debug=True”两个明确源码事实，表中拆为两个 security condition；debug 是描述里的次要根因，不在其主定位行。若采用严格“仅主条件”制度，应分别为 Scout 5、并集 7、新增 2；合计并集 16、新增 4。不能在不同系统间任意切换计数规则。

暂定并集比当前 CodeQL 多匹配到 4 个主条件（或计入明确描述次要条件后的 5 个）gold 根因，说明粗筛有补充线索；**没有证明最终复审链路提升**。产品复审这一轮没有 supported 结论，发现后的确认能力成为瓶颈。

静态匹配包括 label 支持的源码条件，不等同于部署可利用性确认。Flask XML 返回涉及 Python 字节串/字符串兼容性、XXE 涉及依赖版本，均没有运行确认；正式漏洞确认还需原项目 oracle。即使同一行，不同漏洞条件也分开；不同定位行若实际 source→operation/guard 一致，则允许同根因匹配。

## 2. 新增匹配的具体根因

### Flask

- `damn-vulnerable-flask-app-009`：固定 session-signing secret，`app.py:15`，CodeQL 本轮没有该告警。
- `damn-vulnerable-flask-app-010`：注册原始密码进入 `User` 字符串列并 commit，`app.py:26/30/61–63`；Scout 主定位 `login:50` 虽不在 gold 首选行，但其描述明确关联同一持久化链。
- `damn-vulnerable-flask-app-011`（次要条件）：描述明确指出 `app.debug=True`，`app.py:208`；独立于固定 secret，不证明该配置实际部署。

对应复审将 secret/debug 和 plaintext password 判为 `insufficient`。其给出的“数据库是否受保护”“是否有外部哈希”“是否实际部署”等缺失前提，混合了源码安全条件与部署风险可达性。在代码审计制度下，已确认源码缺陷可保留为 source-condition-supported，同时单列 deployment/exploit unknown；不可要求不存在的 WAF/外部保护证据才能描述原始密码存储事实。

### DVNA

- `dvna-007`：`core/authHandler.js:26–32` 的 forgotPw 返回不同 flash 消息和 redirect；`routes/main.js:63` 公共入口可达，账号存在性差异与 gold 同根因。
- `dvna-008`：GET reset 与 POST reset 比较 `md5(login)`，实际谓词位于 `core/authHandler.js:49/78`，`routes/main.js:49/65` 公开绑定。两个 Scout 假设是同一个可预测 token 根因，不算两项新增；原假设主行 `55/84` 是错误分支附近，根因匹配来自完整观察与真实谓词，不是靠行号。

`Product lookup` 假设定位 `modifyProduct` 读取产品。gold `dvna-003` 则是 `userEditSubmit` 以请求 body 中的 user ID 更新其他账号，是不同对象/操作/授权合同。不能因同 CWE/“缺所有权检查”而误记为该 gold 命中。产品模型没有 owner/tenant 字段，且产品列表共享；该假设须核业务授权合同，目前 unknown。

## 3. 确实命中的 FP trap

Flask 的 `damn-vulnerable-flask-app-003` **gold 是 false**，不是被 CodeQL 漏掉的命令注入。

源码 `app.py:4` 是 `from os import popen`；`lookup` 在 `app.py:140` 调用 `rp("nslookup " + address)`。完整文件没有 `rp` 定义、赋值或 import alias；普通请求走到此处先出现未绑定名称，不能凭导入 popen 想象 `rp` 就是 shell wrapper。两条 Scout 假设分别在 139/140 报告同一陷阱，其中一条明确虚构“imported as popen”。

本轮：**1 个 FP trap 根因、2 条重复假设**。CodeQL 没有在该位置报告命令注入；产品复审未决，既没有正确排除这个陷阱，也没有支持它。另四个 Flask trap（参数化 SQLAlchemy 查询、自动转义模板、非敏感 app_name）本轮没有相关候选，不将其“没有报告”写成已完成正确复审。

同文件 eval 已有任意代码执行，理论上可改变模块 globals，但借已有 RCE 注入 `rp` 不构成这个位置的独立命令注入，不以此绕过 trap 定义。

## 4. 复审覆盖与误删

| 项目 | supported | excluded | insufficient | 未评审 | 主要停止原因 |
| --- | --- | --- | --- | --- | --- |
| Flask | 0 | 0 | 4 | 12 | 重复读取/no_progress、模型调用预算耗尽；另 4 条做了保守弃权 |
| DVNA | 0 | 0 | 0 | 43 | 四批取证请求窗口无效或超过 151 行 |

**显式误删 TP 为 0**，因为没有 excluded；这不代表复审通过。Flask 的 eval 两条、固定 secret/debug、原始密码实际具有 gold/source 匹配，却被弃权；DVNA 全部候选未评审。若下游只留下 supported，则本轮所有匹配根因都不能成为已确认输出，应报告确认覆盖缺失，不能把 unknown 默认为 FP、已排除或安全。

Scout 覆盖：Flask 4/4 计划窗口读取，DVNA 7/18；DVNA 未读 routes、passport、用户编辑后半段及部分依赖。完整源码可供工具读取并不等于模型实际看过整个项目。本轮不能推断所有 17 个 DVNA gold 已充分检查。

## 5. 未匹配项保留 unknown

DVNA 有 26 条静态告警未匹配当前 gold：25 条各路由的 missing-rate-limiting、1 条 XML bomb。gold 唯一 brute-force 条目是 `routes/main.js:51–55` 的 POST login，而当前 rate 告警定位其他 auth-check 路由，不能把这些告警按共同 CWE-307 自动计为该 gold 命中，也不能因上游无对应标签直接判 FP。

DVNA 四条 Scout 未匹配：全局上传中间件配置、session 初始化/持久化设置、危险库 imports、product lookup。分别需要实际上传 sink/资源约束、明确 session 威胁合同、真实反序列化调用路径、产品授权语义。只说 `node-serialize` import 危险并没有找出 gold 的 `bulkProductsLegacy → unserialize`，评测器补读源码不能反向把该笼统假设升级为 Scout 检出。

Flask 11 假设均可分到 gold 正根因或一个已定义 trap，但重复很明显；重复报告不提高 root recall。

## 6. systeminformation：29 告警已覆盖同一 root

校准 sanitizer 对象是 `pair-a0a4ebc7815b308f`。CodeQL 本轮的 29 告警中，有 3 条 `js/shell-command-constructed-from-input` 位于 `lib/network.js:1078/1100/1105`。实际 SARIF flow 从外部 library input 进入 networkStats，经过 `lib/network.js:1021` 的 `sanitizeShellString(iface)`，进入 `lib/util.js:488–506` 的字符串替换，再回到 shell command 构造。

原代码 `lib/util.js` 缺换行、制表符、双引号处理，官方补丁改这里；标签 `network.js:1079` 只是下游位置。**根据实际链路，本轮 CodeQL 已覆盖该 input→不充分 sanitizer→shell command root，后续生成单规则命中它不能称新增 CodeQL 漏检能力。**

3 条平台分支告警也不能算 3 个独立 sanitizer 根因。CodeQL 的宽泛告警没有逐分隔符执行验证，因此“已覆盖同 root”与“已经证明特定 payload 可利用”保持不同结论。

## 7. 下一步修正实验制度

1. 保留首轮原始结果；修复窗口参数校验与取证反馈后另立 run ID，不覆盖这批失败/unknown。
2. 将源码安全条件、项目内可达性、部署假设分开。无需真实部署的缺陷判断不能被无限外部前提卡住，缺业务合同的授权假设仍须 unknown。
3. 对 RP 未绑定陷阱做绑定/API 身份取证，不能凭名字/相近 import 认定危险调用。
4. 限定独立 root 计数并拆分 bundled findings，按实际 source/operation/guard 匹配，保留严格主条件统计。
5. 正式比较论文分数前先完成相同任务/版本/模型/预算/成功分母对齐。上述数据是两个开发项目的一轮校准，没有统计显著性，也没有公平复现论文方法，不能宣称胜过作者基线。
