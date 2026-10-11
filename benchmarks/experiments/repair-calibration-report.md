# 修复双 oracle 首轮校准

日期：2026-10-05。**本报告是评测器接入校准，不是平台生成补丁的测试结果，也不是论文 benchmark 的复现分数。** 未调用 LLM、未改产品修复流程、未启动服务/GUI、未安装依赖、未运行上游 PoC。

## 1. 实际完成的工作

- 审查本地六个自然漏洞 JS pre/post 配对的目标函数、官方变更与业务合同。
- 在独立副本执行四组纯函数/模块/回调单元 oracle；Node `v26.0.0`，每个 VM 求值上限 1 秒。
- 从 PatchEval 1,000 条元数据筛到 113 条声明 Python/JS 且测试命令非空记录，排除旧 pilot 仓库后冻结 12 个仓库候选；其中一条实际目标 `.ts`，不能按标签直接算 JS。
- 检查 Vul4Py archive 的 100 条索引，冻结另外最多 8 个未与旧 pilot 仓库重叠的候选。跨资料同根因/别名去重仍待完成。
- 所有自建 oracle 均标记 **derived / agent-authored / not-human-reviewed**，未冒充官方安全测试或人工金标。

源码副本与 SHA256 收据：[source-receipt.json](../../artifacts/research/formal-preparation/repair-calibration/source-receipt.json)。原始完整项目与 pre/post source 保持未改。

## 2. 四项可执行校准结果

| 项目 / API | 原版功能 | 官方修复功能 | 原版安全 | 官方修复安全 | 接纳判断 |
| --- | --- | --- | --- | --- | --- |
| systeminformation / `sanitizeShellString` | 6/6 | 6/6 | 0/3 | 3/3 | 一个有界双 oracle 校准候选；安全范围仅引号/换行/制表符处理 |
| express-fileupload / `processNested` | 4/4 | 4/4 | 0/3 | 2/3 | 严格不接纳；同类路径变体仍污染原型 |
| phantom-html-to-pdf / `page.onResourceRequested` | 5/5 | 4/5 | 0/4 | 4/4 | 暂缓；mock 中 CDN 兼容行为失败，真实引擎语义未验证 |
| forge / `setPath/getPath/deletePath` | 2/2 | 0/2 | 0/1 | 1/1 | 排除语义保持主榜；官方通过移除公开 API 解决问题 |

安全列中的“通过”表示满足指定安全断言。原版安全失败是校准期预期现象，不是测试器错误。本轮 **没有得到 4–6 个正式接纳任务**：只有一个有限边界候选通过自建双 oracle，尚需人审/完整根因核定，正式可评分任务数仍为 0。

### systeminformation：可先接入修复 runner 的有限候选

完整 `lib/util.js` 在无 child_process/fs 能力的 VM 中载入，调用导出 `sanitizeShellString`。正常样例覆盖常见接口名、带空格/冒号/点号的名字，安全样例检查三种输入分隔符被删除。实际下游 `lib/network.js` 使用该结果组装命令，因此存在源码关联；**没有运行命令，不能据此声称完整命令注入已验证或所有接口名/平台行为均保持**。

上游标注是 `lib/network.js:1079`，该文件 pre/post 未改变；实际补丁是 `lib/util.js`。规则/修复定位应按根因与调用链，不能只匹配标注行。

### express-fileupload：安全 oracle 不能只覆盖补丁写出的黑名单

正常断言覆盖平坦字段、方括号数组、嵌套对象、点号路径、空输入。两个 `__proto__` 变体在修复后通过；`constructor.prototype` 路径在同一模块内仍修改 VM 自身 `Object.prototype`。未污染宿主全局对象、未运行任何系统利用。若只测试补丁新增的 `__proto__` 黑名单，会错误地把不完整修复评为全部正确。

可保留为“官方补丁不足”的开发诊断任务；在人工裁决前不以官方 post 作为完全安全负例，不缩小 oracle 以换取漂亮分数。

### phantom-html-to-pdf：环境替代会影响结论

执行完整转换脚本，但 `page.open` 为惰性 stub，导航回调不执行；`abort/changeUrl` 只记内存状态。协议检查显示原版允许非 HTTP(S) 的部分字符串、修复版拒绝它们，无真实文件/网络读取。

正常合同还包括源码明确说明的 scheme-relative CDN 重写。mock 的 `changeUrl` 不改变 `request.url`，修复版随后触发拒绝；真实 PhantomJS 对请求对象是否同步变更尚未验证。因此这不是已证实的真实引擎回归，不能将 mock 推断升级为产品漏洞或正式安全 oracle。按照不启动浏览器/服务的范围，本项暂缓。

上游标注的 `lib/conversion.js` pre/post 未改变，实际补丁位于 `lib/scripts/conversionScriptPart.js`。

### forge：删除危险 API 不等于保持业务语义

读取并执行三个完整路径函数的原始连续源码切片。原版正常嵌套设置、读取、删除保持兄弟字段；修复版删除全部三个函数，安全断言通过但正常 API 合同失败。上游主动弃用危险 API 可以是合理修复路线，但与本平台“保持原有可用业务 API”的任务定义不兼容，故不进入同一修复正确率分母。

## 3. 两个暂不能可靠单元化的完整配对

- `scratch-svg-renderer`：`loadString → _transformMeasurements` 涉及 DOMParser、真实 DOM 挂载、`getBBox` 与 DOMPurify 2.1.1。用返回“已清洗”字符串的假 DOMPurify 会直接把 gold 行为写进 mock，不能证明 XSS/业务尺寸保持。不安装依赖/启浏览器，因此未执行。
- `angular.js`：`jqLiteBuildFragment` 的 XHTML 重写与 DOM 解析结果/旧 IE wrapper 行为紧密相关。只比较字符串或伪造 DOM 不能确认浏览器解析后的脚本语义，不作为本阶段纯单元任务。

## 4. PatchEval / Vul4Py 的下一步

PatchEval 命令经常自带 `git apply /workspace/fix.patch` 或 Docker `/workspace/PoC_env/...` 路径。不能直接把命令返回成功当作原版正常功能通过，也不能把这类路径当作本地已有完整项目。本轮不执行这些脚本。

最值得先下载完整固定源码再校准的纯模块候选：

| 候选 | 待验证 API / 合同 | 当前不能执行的原因 |
| --- | --- | --- |
| h11 `CVE-2025-43859` | `ChunkedReader` 字节流解析；有效 chunk/分段读取保持，非法 CRLF 拒绝 | 只有函数片段/元数据，没有 ReceiveBuffer/完整 pre/post 项目和测试 |
| snowflake-connector-python `CVE-2024-49750` | `SecretDetector` 日志脱敏；正常文本保持、敏感 token 不外泄 | 元数据片段只有类常量，缺完整方法/项目；不能把片段拼成 gold |
| langchain `CVE-2024-3571` | `LocalFileStore._get_full_path`；正常 key 保持，越界 key 被拒绝 | 只有片段和缩短 commit，需固定完整 SHA/源码/依赖合同 |
| undici `CVE-2024-30260` | redirect handler 的 header/URL 重定向合同 | 完整源与测试依赖未下载；需确认是否能纯 mock HTTP 消息验证 |

其他冻结候选包括 spotipy/gradio/mongoose/django/airflow/mlflow/express，通常依赖/服务合同更重。fedify 目标是 TypeScript，单列支持边界。完整筛选收据：[metadata-shortlist.json](../../artifacts/research/formal-preparation/repair-calibration/metadata-shortlist.json)。Vul4Py 只有索引和脚本，没有完整 vulnerable/fixed checkouts，暂不新增运行分数。

## 5. 可重复命令与下一步验收

在仓库根目录执行：

```bash
node artifacts/research/formal-preparation/repair-calibration/unit_oracles.cjs
```

脚本默认使用已保存的单文件独立副本，生成 [unit-oracle-results.json](../../artifacts/research/formal-preparation/repair-calibration/unit-oracle-results.json)。可用两个位置参数指定同结构 source root 与 receipt 文件，便于后续在候选补丁副本中执行。每项断言结果单独存储；脚本本身退出 0 只代表完整生成收据，**不代表所有 oracle 通过**。

接下来先取得 h11 等独立 Python 完整源码，复核业务不变量与原/修复双 oracle。再冻结可见/隐藏划分、模型修复预算并对照语义上下文消融。新修复版本必须分别报告：定位正确、补丁可应用、功能保持、安全通过、未知/环境失败，不能从上述上游补丁校准结果推断本平台有提升。
